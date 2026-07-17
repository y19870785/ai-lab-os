# ADR-047：Read On Ambiguity And Explicit Write Commands

状态：Proposed / SP-012 implementation candidate

## Decision

有歧义时不写入。Work Log 必须包含显式记录命令或明确已发生动作；“今天”“刚才”“会议”等宽泛词不能单独触发写入。Reminder 查询别名在 Work Log 规则之前判定。

## Consequences

普通疑问句不会产生持久化副作用。合法的“记录一下…”以及“今天完成了…”仍保持兼容；无法可靠分类的输入进入 Chat，而不是猜测写操作。
