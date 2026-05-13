# retailpulses-agent-skills

Retailpulses GK 的 Accio Agent Skills 定义仓库。Skills 是"操作能力包"——不是零散 prompt，而是结构化的可复用技能定义。

## 作用

- **Agent Skills 的版本管理** — 所有 agent-level 和 account-level 的 SKILL.md 和配置
- **跨机器部署** — clone 后在目标电脑上由 Accio Agent 负责安装到 `.accio/` 目录
- **知识资产沉淀** — 模板、检查清单、输入输出 schema

> Skills 不包含可执行代码。所有工具服务请参见 [retailpulses-tool-services](https://github.com/Retailpules/retailpulses-tool-services)。

## 目录结构

```
├── skills/               # Skill 定义
│   ├── agent/            # Agent-level skills
│   └── account/          # Account-level skills
├── templates/            # Prompt / 回复模板
├── examples/             # 输入输出示例
├── checklists/           # QA 检查清单
└── docs/
```

## Skill 标准化结构

每个 skill 目录包含：

```
skill-name/
├── SKILL.md              # purpose / scenarios / rules / forbidden actions
├── input.schema.json     # 输入参数 schema
├── output.schema.json    # 输出格式 schema
├── examples/             # 使用示例
├── checklist.md          # 使用前后质量检查
└── changelog.md          # 版本历史
```

详见 [docs/skill-structure-guide.md](docs/skill-structure-guide.md)
