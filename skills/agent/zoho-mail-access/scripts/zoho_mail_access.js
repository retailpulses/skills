#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_MAIL_BASE = 'https://mail.zoho.com/api';
const DEFAULT_ACCOUNTS_DOMAIN = 'accounts.zoho.com';
const REQUIRED_KEYS = ['ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET', 'ZOHO_REFRESH_TOKEN'];
const DEFAULT_OUTPUT_ROOT = ['deliverables', 'zoho-mail'];

main().catch((err) => {
  console.error(err && err.message ? err.message : String(err));
  process.exit(1);
});

async function main() {
  const rawArgs = process.argv.slice(2);
  if (!rawArgs.length || rawArgs.some((token) => token === '--help' || token === '-h' || token === 'help')) {
    printUsage();
    return;
  }

  const args = parseArgs(rawArgs);
  const command = args._[0] || 'capture';

  const context = loadWorkspaceContext();
  const cfg = context.config;
  validateCredentials(cfg);

  const accountsDomain = cfg.ACCOUNTS_DOMAIN || cfg.ZOHO_ACCOUNTS_DOMAIN || DEFAULT_ACCOUNTS_DOMAIN;
  const mailBase = cfg.ZOHO_MAIL_BASE || DEFAULT_MAIL_BASE;
  const accessToken = await refreshAccessToken(cfg, accountsDomain);
  const accountId = cfg.ZOHO_ACCOUNT_ID || (await resolveAccountId(accessToken, mailBase));
  const folderMode = String(args.folder || 'inbox').trim();
  const subjectFilter = String(args.subject || '').trim();
  const keywords = splitKeywords(args.keywords);
  const keywordMode = String(args['keyword-mode'] || 'any').toLowerCase() === 'all' ? 'all' : 'any';
  const recentHours = toInt(args['recent-hours'], 0);
  const limit = clampInt(toInt(args.limit, 200), 1, 200);
  const maxPages = clampInt(toInt(args['max-pages'], 20), 1, 200);
  const includeContent = args['include-content'] !== 'false';
  const outputDir = resolveOutputDir(context.rootDir, args['capture-dir'], subjectFilter, keywords);

  const folderId = await resolveFolderId({
    mailBase,
    accountId,
    accessToken,
    folderMode,
    forcedFolderId: cfg.ZOHO_INBOX_FOLDER_ID,
  });

  const messages = await searchMessages({
    mailBase,
    accountId,
    accessToken,
    folderMode,
    folderId,
    subjectFilter,
    keywords,
    keywordMode,
    recentHours,
    limit,
    maxPages,
    includeContent,
  });

  if (command === 'search') {
    writeJson(process.stdout, {
      ok: true,
      accountId,
      folderMode,
      folderId,
      count: messages.length,
      messages,
    });
    return;
  }

  const bundle = buildCaptureBundle({
    context,
    accountId,
    folderMode,
    folderId,
    subjectFilter,
    keywords,
    keywordMode,
    recentHours,
    messages,
  });
  writeCaptureBundle(outputDir, bundle);
  process.stdout.write(`${outputDir}\n`);
}

function loadWorkspaceContext() {
  const roots = unique([
    process.cwd(),
    __dirname,
    path.resolve(__dirname, '..'),
    path.resolve(__dirname, '..', '..'),
    path.resolve(__dirname, '..', '..', '..'),
  ]);
  const rootDir = findRepoRoot(roots);
  const config = {};
  for (const file of [
    path.join(rootDir, 'dev.env'),
    path.join(rootDir, '.env'),
    path.join(rootDir, 'variables and secrets.txt'),
  ]) {
    if (!fs.existsSync(file)) continue;
    Object.assign(config, parseEnvLikeFile(fs.readFileSync(file, 'utf8')));
  }
  for (const [key, value] of Object.entries(process.env)) {
    if (value !== undefined && value !== '') config[key] = value;
  }
  return { rootDir, config };
}

function findRepoRoot(candidates) {
  for (const start of candidates) {
    let dir = path.resolve(start);
    for (let depth = 0; depth < 8; depth += 1) {
      if (fs.existsSync(path.join(dir, 'dev.env')) || fs.existsSync(path.join(dir, '.git'))) {
        return dir;
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  return path.resolve(process.cwd());
}

function parseEnvLikeFile(raw) {
  const out = {};
  for (const line of String(raw || '').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx < 0) continue;
    const key = trimmed.slice(0, idx).trim();
    let value = trimmed.slice(idx + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

function validateCredentials(cfg) {
  const missing = REQUIRED_KEYS.filter((key) => !String(cfg[key] || '').trim());
  if (missing.length) {
    throw new Error(`Missing Zoho credential(s): ${missing.join(', ')}`);
  }
}

async function refreshAccessToken(cfg, accountsDomain) {
  const form = new URLSearchParams();
  form.set('grant_type', 'refresh_token');
  form.set('refresh_token', cfg.ZOHO_REFRESH_TOKEN);
  form.set('client_id', cfg.ZOHO_CLIENT_ID);
  form.set('client_secret', cfg.ZOHO_CLIENT_SECRET);

  const res = await fetch(`https://${accountsDomain}/oauth/v2/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  const body = await readResponseBody(res);
  if (!res.ok || !body || !body.access_token) {
    throw new Error(`Zoho token refresh failed: ${JSON.stringify(safeSummary(body))}`);
  }
  return body.access_token;
}

async function resolveAccountId(accessToken, mailBase) {
  const res = await fetch(`${mailBase}/accounts`, {
    headers: { Authorization: `Zoho-oauthtoken ${accessToken}` },
  });
  const body = await readResponseBody(res);
  if (!res.ok) {
    throw new Error(`Zoho account lookup failed: ${JSON.stringify(safeSummary(body))}`);
  }
  const items = extractArray(body);
  for (const item of items) {
    const accountId = firstString(item, ['accountId', 'accountid', 'id', 'account_id']);
    if (accountId) return accountId;
  }
  throw new Error('Unable to resolve Zoho account ID from /accounts response');
}

async function resolveFolderId({ mailBase, accountId, accessToken, folderMode, forcedFolderId }) {
  if (folderMode && folderMode !== 'inbox' && folderMode !== 'all') return folderMode;
  if (forcedFolderId && folderMode !== 'all') return String(forcedFolderId);
  const res = await fetch(`${mailBase}/accounts/${encodeURIComponent(accountId)}/folders`, {
    headers: { Authorization: `Zoho-oauthtoken ${accessToken}` },
  });
  const body = await readResponseBody(res);
  if (!res.ok) return null;
  const items = extractArray(body);
  for (const item of items) {
    const name = String(firstString(item, ['folderName', 'foldername', 'name']) || '').toLowerCase();
    const folderId = firstString(item, ['folderId', 'folderid', 'id']);
    if (!folderId) continue;
    if (name === 'inbox' || name.includes('inbox')) return folderId;
  }
  const first = items[0];
  return first ? firstString(first, ['folderId', 'folderid', 'id']) || null : null;
}

async function searchMessages({
  mailBase,
  accountId,
  accessToken,
  folderMode,
  folderId,
  subjectFilter,
  keywords,
  keywordMode,
  recentHours,
  limit,
  maxPages,
  includeContent,
}) {
  const matches = [];
  const seen = new Set();
  const sinceMs = recentHours > 0 ? Date.now() - recentHours * 60 * 60 * 1000 : 0;
  const pages = [];
  for (let page = 0; page < maxPages; page += 1) {
    const start = 1 + page * limit;
    const url = buildListUrl(mailBase, accountId, folderMode, folderId, start, limit);
    const res = await fetch(url, { headers: { Authorization: `Zoho-oauthtoken ${accessToken}` } });
    const body = await readResponseBody(res);
    if (!res.ok) {
      throw new Error(`Zoho message list failed at start=${start}: ${JSON.stringify(safeSummary(body))}`);
    }
    const batch = extractArray(body);
    if (!batch.length) break;
    pages.push({ start, count: batch.length });
    for (const rawMessage of batch) {
      const message = normalizeMessage(rawMessage);
      if (!message.messageId || seen.has(message.messageId)) continue;
      seen.add(message.messageId);
      if (sinceMs && message.receivedMs && message.receivedMs < sinceMs) continue;
      if (subjectFilter && !includesSafe(message.subject, subjectFilter)) continue;
      if (!keywords.length) {
        matches.push({ ...message, matchedOn: subjectFilter ? ['subject'] : [] });
        continue;
      }
      const subjectMatch = keywordsMatch(subjectFilter ? message.subject : '', keywords, keywordMode);
      let bodyText = '';
      let bodyHtml = '';
      if (!subjectMatch && includeContent) {
        const content = await fetchMessageContent({
          mailBase,
          accountId,
          accessToken,
          message,
          fallbackFolderId: folderId,
        });
        bodyText = content.bodyText;
        bodyHtml = content.bodyHtml;
      }
      const haystack = `${message.subject}\n${message.fromAddress}\n${message.snippet}\n${bodyText}\n${bodyHtml}`;
      if (!keywordsMatch(haystack, keywords, keywordMode)) continue;
      const content = bodyText || bodyHtml ? { bodyText, bodyHtml } : includeContent
        ? await fetchMessageContent({
            mailBase,
            accountId,
            accessToken,
            message,
            fallbackFolderId: folderId,
          })
        : { bodyText: '', bodyHtml: '' };
      matches.push({
        ...message,
        bodyText: content.bodyText,
        bodyHtml: content.bodyHtml,
        matchedOn: describeMatches(message, subjectFilter, keywords, keywordMode, content.bodyText, content.bodyHtml),
      });
    }
    if (batch.length < limit) break;
  }
  if (includeContent) {
    for (const item of matches) {
      if (item.bodyText || item.bodyHtml) continue;
      const content = await fetchMessageContent({
        mailBase,
        accountId,
        accessToken,
        message: item,
        fallbackFolderId: folderId,
      });
      item.bodyText = content.bodyText;
      item.bodyHtml = content.bodyHtml;
      if (!item.matchedOn.length) {
        item.matchedOn = describeMatches(item, subjectFilter, keywords, keywordMode, item.bodyText, item.bodyHtml);
      }
    }
  }
  matches.sort((a, b) => (b.receivedMs || 0) - (a.receivedMs || 0));
  return matches;
}

function buildListUrl(mailBase, accountId, folderMode, folderId, start, limit) {
  const base = `${mailBase}/accounts/${encodeURIComponent(accountId)}/messages/view`;
  if (folderMode === 'all') return `${base}?start=${start}&limit=${limit}`;
  if (folderId) return `${base}?folderId=${encodeURIComponent(folderId)}&start=${start}&limit=${limit}`;
  return `${base}?start=${start}&limit=${limit}`;
}

async function fetchMessageContent({ mailBase, accountId, accessToken, message, fallbackFolderId }) {
  const folderId = message.folderId || fallbackFolderId;
  if (!folderId || !message.messageId) return { bodyText: '', bodyHtml: '' };
  const url = `${mailBase}/accounts/${encodeURIComponent(accountId)}/folders/${encodeURIComponent(folderId)}/messages/${encodeURIComponent(message.messageId)}/content`;
  const res = await fetch(url, { headers: { Authorization: `Zoho-oauthtoken ${accessToken}` } });
  const body = await readResponseBody(res);
  if (!res.ok) return { bodyText: '', bodyHtml: '' };
  const html = String(firstString(body, ['data.content', 'content']) || '');
  return { bodyText: htmlToText(html), bodyHtml: html };
}

function normalizeMessage(raw) {
  const messageId = firstString(raw, ['messageId', 'messageid', 'id']) || '';
  const subject = firstString(raw, ['subject']) || '';
  const fromAddress = firstString(raw, ['fromAddress', 'fromaddress', 'from', 'sender']) || '';
  const toAddress = firstString(raw, ['toAddress', 'toaddress', 'to']) || '';
  const snippet = firstString(raw, ['summary', 'snippet', 'preview', 'shortContent', 'bodyPreview']) || '';
  const folderId = firstString(raw, ['folderId', 'folderid', 'folder_id']) || '';
  const receivedRaw = firstValue(raw, ['receivedTime', 'receivedtime', 'receivedTimeInMillis', 'receivedtimeInMillis', 'receivedDate', 'receiveddate']);
  const receivedMs = parseReceivedMs(receivedRaw);
  return {
    messageId,
    subject,
    fromAddress,
    toAddress,
    snippet,
    folderId,
    receivedRaw: receivedRaw == null ? '' : String(receivedRaw),
    receivedMs,
    receivedIso: receivedMs ? new Date(receivedMs).toISOString() : '',
  };
}

function describeMatches(message, subjectFilter, keywords, keywordMode, bodyText, bodyHtml) {
  const matched = [];
  if (subjectFilter && includesSafe(message.subject, subjectFilter)) matched.push('subject');
  const haystack = `${message.subject}\n${message.fromAddress}\n${message.snippet}\n${bodyText}\n${bodyHtml}`;
  for (const keyword of keywords) {
    if (includesSafe(haystack, keyword)) matched.push(keyword);
  }
  if (!subjectFilter && !keywords.length) matched.push(keywordMode === 'all' ? 'all' : 'any');
  return matched;
}

function keywordsMatch(source, keywords, mode) {
  if (!keywords.length) return true;
  if (mode === 'all') return keywords.every((keyword) => includesSafe(source, keyword));
  return keywords.some((keyword) => includesSafe(source, keyword));
}

function includesSafe(source, needle) {
  return String(source || '').toLowerCase().includes(String(needle || '').toLowerCase());
}

function splitKeywords(value) {
  return String(value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

function firstValue(obj, paths) {
  for (const pathSpec of paths) {
    const value = getByPath(obj, pathSpec);
    if (value !== undefined && value !== null && String(value).trim() !== '') return value;
  }
  return '';
}

function firstString(obj, paths) {
  const value = firstValue(obj, paths);
  return value === undefined || value === null ? '' : String(value);
}

function getByPath(obj, pathSpec) {
  const parts = String(pathSpec).split('.');
  let cur = obj;
  for (const part of parts) {
    if (cur == null || typeof cur !== 'object') return undefined;
    cur = cur[part];
  }
  return cur;
}

function extractArray(body) {
  const candidates = [
    body,
    body && body.data,
    body && body.messages,
    body && body.data && body.data.messages,
    body && body.data && body.data.folders,
    body && body.folders,
    body && body.data && body.data.accounts,
  ];
  for (const candidate of candidates) {
    if (Array.isArray(candidate)) return candidate;
  }
  return [];
}

function parseReceivedMs(value) {
  if (value == null || value === '') return 0;
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 1e12 ? Math.floor(value) : Math.floor(value * 1000);
  }
  const str = String(value).trim();
  if (/^\d{13}$/.test(str)) return Number(str);
  if (/^\d{10}$/.test(str)) return Number(str) * 1000;
  const parsed = Date.parse(str);
  return Number.isFinite(parsed) ? parsed : 0;
}

async function readResponseBody(res) {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

function htmlToText(html) {
  return String(html || '')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/p>/gi, '\n')
    .replace(/<\/div>/gi, '\n')
    .replace(/<\/li>/gi, '\n')
    .replace(/<[^>]+>/g, '')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\r\n/g, '\n')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .replace(/[ \t]{2,}/g, ' ')
    .trim();
}

function buildCaptureBundle({ context, accountId, folderMode, folderId, subjectFilter, keywords, keywordMode, recentHours, messages }) {
  const generatedAt = new Date().toISOString();
  return {
    generatedAt,
    accountId,
    folderMode,
    folderId,
    subjectFilter,
    keywords,
    keywordMode,
    recentHours,
    count: messages.length,
    sourceFiles: context.config ? ['dev.env', '.env', 'variables and secrets.txt'] : [],
    messages,
    markdown: renderMarkdownCapture({
      generatedAt,
      accountId,
      folderMode,
      folderId,
      subjectFilter,
      keywords,
      keywordMode,
      recentHours,
      messages,
    }),
  };
}

function renderMarkdownCapture(bundle) {
  const lines = [];
  lines.push(`# Zoho Mail Capture`);
  lines.push('');
  lines.push(`- Generated at: ${bundle.generatedAt}`);
  lines.push(`- Account ID: ${bundle.accountId}`);
  lines.push(`- Folder mode: ${bundle.folderMode}`);
  lines.push(`- Folder ID: ${bundle.folderId || ''}`);
  lines.push(`- Subject filter: ${bundle.subjectFilter || ''}`);
  lines.push(`- Keywords: ${bundle.keywords.join(', ')}`);
  lines.push(`- Keyword mode: ${bundle.keywordMode}`);
  lines.push(`- Recent hours: ${bundle.recentHours || ''}`);
  lines.push(`- Match count: ${bundle.messages.length}`);
  lines.push('');
  for (const [index, msg] of bundle.messages.entries()) {
    lines.push(`## ${index + 1}. ${msg.subject || '(no subject)'}`);
    lines.push(`- Message ID: ${msg.messageId || ''}`);
    lines.push(`- From: ${msg.fromAddress || ''}`);
    lines.push(`- To: ${msg.toAddress || ''}`);
    lines.push(`- Received: ${msg.receivedIso || msg.receivedRaw || ''}`);
    lines.push(`- Folder ID: ${msg.folderId || ''}`);
    lines.push(`- Matched on: ${(msg.matchedOn || []).join(', ')}`);
    if (msg.snippet) {
      lines.push('');
      lines.push(`> ${msg.snippet.replace(/\n/g, '\n> ')}`);
    }
    const body = String(msg.bodyText || '').trim();
    if (body) {
      lines.push('');
      lines.push('```text');
      lines.push(body);
      lines.push('```');
    }
    lines.push('');
  }
  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

function writeCaptureBundle(outputDir, bundle) {
  fs.mkdirSync(outputDir, { recursive: true });
  fs.writeFileSync(path.join(outputDir, 'capture.json'), JSON.stringify(bundle, null, 2) + '\n', 'utf8');
  fs.writeFileSync(path.join(outputDir, 'capture.md'), bundle.markdown, 'utf8');
  fs.writeFileSync(
    path.join(outputDir, 'manifest.json'),
    JSON.stringify(
      {
        generatedAt: bundle.generatedAt,
        accountId: bundle.accountId,
        count: bundle.messages.length,
        subjectFilter: bundle.subjectFilter,
        keywords: bundle.keywords,
      },
      null,
      2
    ) + '\n',
    'utf8'
  );
}

function resolveOutputDir(rootDir, explicitDir, subjectFilter, keywords) {
  if (explicitDir) return path.resolve(rootDir, explicitDir);
  const stamp = formatStamp(new Date());
  const subjectPart = slugify(subjectFilter || (keywords.length ? keywords.join('-') : 'capture'));
  return path.join(rootDir, ...DEFAULT_OUTPUT_ROOT, `${stamp}-${subjectPart}`);
}

function formatStamp(date) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}-${pad(date.getHours())}${pad(date.getMinutes())}${pad(date.getSeconds())}`;
}

function slugify(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 48) || 'capture';
}

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    if (!token.startsWith('--')) {
      out._.push(token);
      continue;
    }
    const eq = token.indexOf('=');
    if (eq >= 0) {
      const key = token.slice(2, eq);
      const value = token.slice(eq + 1);
      out[key] = value;
      continue;
    }
    const key = token.slice(2);
    const next = argv[i + 1];
    if (next && !next.startsWith('--')) {
      out[key] = next;
      i += 1;
    } else {
      out[key] = true;
    }
  }
  return out;
}

function toInt(value, fallback) {
  const n = Number.parseInt(String(value || ''), 10);
  return Number.isFinite(n) ? n : fallback;
}

function clampInt(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function safeSummary(body) {
  if (!body || typeof body !== 'object') return body;
  const out = {};
  for (const key of ['error', 'message', 'status', 'code', 'success']) {
    if (body[key] !== undefined) out[key] = body[key];
  }
  if (Object.keys(out).length) return out;
  return body;
}

function writeJson(stream, value) {
  stream.write(JSON.stringify(value, null, 2) + '\n');
}

function unique(items) {
  return [...new Set(items.filter(Boolean))];
}

function printUsage() {
  process.stdout.write(
    [
      'Usage:',
      '  node scripts/zoho_mail_access.js capture --subject "..." --keywords "foo,bar" [--capture-dir ./deliverables/zoho-mail/run1]',
      '  node scripts/zoho_mail_access.js search --subject "..." --keywords "foo,bar"',
      '',
      'Options:',
      '  --folder inbox|all|<folderId>',
      '  --recent-hours <n>',
      '  --limit <n>',
      '  --max-pages <n>',
      '  --keyword-mode any|all',
      '  --include-content true|false',
    ].join('\n') + '\n'
  );
}
