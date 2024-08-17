# grafana-tool_reporter

    ⚠ 开发进行中，尚不可用。

一个工具，用于将Grafana仪表板呈现为PNG、HTML、PDF格式，并使用各种工具将它们发送到指定的目的地。

# Schedule 配置说明

注意，虽然程序使用了 schedule 库，但是并不支持所有的 schedule 语法。作为报表推送，太小时间粒度的报表，似乎没有意义，比如分钟级监控或者小时级别监控数据，直接使用 Grafana 要更好。

### every
1. 可以用 n day 表示每几天执行一次，例如 `1 day`, `10 day`。
2. 可以用 n week 表示每几周执行一次，例如 `1 week`, `2 week`。
3. 可以用 1 month 表示每月执行一次，不支持多个月。

### at_time
1. 具体执行的时间，24小时制，例如 `10:30`

### at_week
1. 只在每周或者每几周运行时有用，具体的星期，例如 `Sunday` `Monday` `Tuesday` `Wednesday` `Thursday` `Friday` `Saturday`

### at_month
1. 只在每月执行时有用，表示每月的第几天执行，例如 `3`