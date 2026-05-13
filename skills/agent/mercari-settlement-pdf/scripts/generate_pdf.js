const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

function parseArgs(argv) {
  const options = {
    number: 'INV-2026-0X',
    issueDate: new Date().toLocaleDateString('ja-JP', { year: 'numeric', month: 'long', day: 'numeric' }),
    data: [],
    output: '',
  };

  for (const arg of argv) {
    if (!arg.startsWith('--')) continue;
    const [key, rawValue = ''] = arg.slice(2).split('=');
    const value = rawValue.trim();

    if (key === 'number' && value) options.number = value;
    if (key === 'issue-date' && value) options.issueDate = value;
    if (key === 'data' && value) options.data = JSON.parse(value);
    if (key === 'output' && value) options.output = value;
  }

  if (!options.output) {
      options.output = path.resolve(__dirname, '..', `売上金精算書_${options.number}.pdf`);
  }

  return options;
}

const options = parseArgs(process.argv.slice(2));

// Calculate total
const total = options.data.reduce((acc, curr) => acc + parseInt(curr.amount.replace(/,/g, '')), 0);
const formattedTotal = new Intl.NumberFormat('ja-JP').format(total);

const rowsHtml = options.data.map(row => `
    <tr>
        <td>${row.month} 売上金精算額</td>
        <td style="text-align: right;">${row.amount}</td>
    </tr>
`).join('');

const html = `
<!doctype html>
<html lang="ja">
<head>
    <meta charset="utf-8">
    <title>売上金精算书</title>
    <style>
        @page { size: A4; margin: 15mm; }
        body { font-family: "Hiragino Sans", sans-serif; line-height: 1.5; color: #222; font-size: 15px; margin: 0; padding: 0; }
        .title { text-align: center; font-size: 26px; font-weight: bold; margin-bottom: 30px; text-decoration: underline; letter-spacing: 0.1em; }
        .header { display: flex; justify-content: space-between; margin-bottom: 25px; align-items: flex-start; }
        .recipient { font-size: 17px; border-bottom: 2px solid #333; padding-bottom: 6px; width: 48%; }
        .recipient-address { font-size: 13px; margin-top: 6px; line-height: 1.5; }
        .issuer { text-align: right; width: 48%; font-size: 13px; line-height: 1.5; }
        .issuer-name { font-size: 15px; font-weight: bold; margin-bottom: 4px; }
        .subject { font-size: 17px; font-weight: bold; margin-bottom: 20px; border-left: 6px solid #333; padding: 8px 15px; background: #f2f2f2; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 25px; }
        th, td { border: 1px solid #888; padding: 12px; text-align: left; }
        th { background-color: #f7f7f7; width: 70%; font-size: 15px; }
        td { font-size: 15px; }
        .total-row { font-weight: bold; font-size: 18px; background-color: #f0f0f0; }
        .bank-info { background-color: #fafafa; padding: 15px 20px; border-radius: 6px; margin-bottom: 25px; border: 1px solid #ddd; }
        .bank-info h3 { margin-top: 0; font-size: 15px; border-bottom: 1px solid #aaa; padding-bottom: 6px; margin-bottom: 12px; }
        .bank-grid { display: grid; grid-template-columns: 110px 1fr; gap: 8px; font-size: 14px; }
        .note { font-size: 14px; color: #111; white-space: pre-wrap; line-height: 1.65; border-top: 1px solid #ccc; padding-top: 15px; }
        .note b { font-size: 15px; display: block; margin-bottom: 8px; }
    </style>
</head>
<body>
    <div class="title">売上金精算書</div>
    
    <div class="header">
        <div class="recipient">
            <div>合同会社リンセイ 御中</div>
            <div class="recipient-address">
                〒124-0011<br>
                東京都葛飾区四つ⽊2-20-4-301
            </div>
        </div>
        <div class="issuer">
            <div class="issuer-name">リテルパルス合同会社</div>
            <div>〒124-0011 東京都葛飾区四つ木二丁目20番4号202号</div>
            <div style="margin-top: 6px;">発行日：${options.issueDate}</div>
            <div>精算書番号：${options.number}</div>
        </div>
    </div>

    <div class="subject">件名：メルカリショップ売上金精算（${options.data[0].month}～${options.data[options.data.length-1].month}）</div>
    <p style="margin-bottom: 12px; font-size: 15px;">下記の通り、売上金の精算をお願い申し上げます。</p>

    <table>
        <thead>
            <tr>
                <th>摘要</th>
                <th style="text-align: center;">金額（円）</th>
            </tr>
        </thead>
        <tbody>
            ${rowsHtml}
            <tr class="total-row">
                <td style="text-align: right;">精算金額合計</td>
                <td style="text-align: right;">¥ ${formattedTotal}</td>
            </tr>
        </tbody>
    </table>

    <div class="bank-info">
        <h3>【振込先】</h3>
        <div class="bank-grid">
            <div>銀行名</div><div>楽天銀行</div>
            <div>支店名</div><div>第四営業支店 (支店番号：254)</div>
            <div>口座名義</div><div>リテルパルス（ド</div>
            <div>口座番号</div><div>普通 7715880</div>
        </div>
    </div>

    <div class="note"><b>【備考】</b>
貴社名義のメルカリショップ「ホムブリス・２号店」の店舗において受領済みの売上金のうち、当社が实質的に販売・運営を行い、商品在庫、返品対応その他一切の経営リスクを負担した対象取引分につき、当社帰属額の精算をお願い申し上げます。

対象期間は${options.data[0].month}から${options.data[options.data.length-1].month}までです。なお、振込手数料は当社にて負担いたします。</div>
</body>
</html>
`;

async function main() {
    const browser = await chromium.launch({
        headless: true,
        executablePath: CHROME_PATH,
    });
    const page = await browser.newPage();
    await page.setContent(html);
    await page.pdf({
        path: options.output,
        format: 'A4',
        printBackground: true,
    });
    await browser.close();
    console.log(`PDF generated at: ${options.output}`);
}

main().catch(console.error);
