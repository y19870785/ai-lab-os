# ADR-047：Read On Ambiguity And Explicit Write Commands

状态：Accepted

**Accepted by:** SP-012 · PR [#25](https://github.com/y19870785/ai-lab-os/pull/25) · Merge Commit `d550ab8757b50e4d12587d5e71a0058089bd3821`

## Decision

有歧义时不写入。Work Log 必须包含显式记录命令或明确已发生动作；“今天”“刚才”“会议”等宽泛词不能单独触发写入。Reminder 查询别名在 Work Log 规则之前判定。

## Consequences

普通疑问句不会产生持久化副作用。合法的“记录一下…”以及“今天完成了…”仍保持兼容；无法可靠分类的输入进入 Chat，而不是猜测写操作。
