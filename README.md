# grafana-tool_reporter

    ⚠ 尚未测试，不保证可用性。

一个工具，用于将Grafana仪表板呈现为PNG、HTML、PDF格式，并使用各种工具将它们发送到指定的目的地。

### TODO
- [ ] 使用 AI 总结页面数据
- [ ] 添加 Email 作为推送器
- [ ] 使用 S3 兼容的对象存储来保存文件，以避免需要本地架设web服务


# 配置说明

在 config 目录中：

### config.yaml

```YAML
grafana:
  # 程序自身可访问的 grafna 地址，可以使用内网地址，只要本程序可以访问即可
  public_url: https://your-grafana.com
  # 在 Grafana 后台中创建一个服务账户，即可获得 token
  token: your-token
files:
  # 本程序中 web 服务的访问地址，目前必须是公网可访问地址，否则否则某些只能
  # 从网络URL发送文件的推送器将无法下载到图片或文件。
  public_url: https://example.com
  # 产生的临时文件保存天数
  expiry_days: 2
```

### notifier.yaml

目前仅支持文件中列出项作为推送器，可以将不用的推送器删除或注释，但是不支持自行添加推送器。

```YAML
DingTalkWebhook:
  # 钉钉 WEBHOOK 机器人，只能发送文本和图片，文件只会以明文链接形式发送。
  # 无需更改默认的 uri 配置，从钉钉复制的 webhook 地址中，access_token
  # 等号后面的部分需要填写到 job.yaml 作为 receiver
  # 
  # 在 job.yaml 中的使用方法：
  # notifier:
  #   type: DingTalkWebhook
  #   receiver:
  #     - access_token_1
  #     - access_token_2
  uri: https://oapi.dingtalk.com/robot/send
  
Gotify:
  # 只能发送文本和图片，文件只会以明文链接形式发送。
  # 无需更改默认的 uri 配置，token 需要填写到 job.yaml 作为 receiver
  # 
  # 在 job.yaml 中的使用方法：
  # notifier:
  #   type: Gotify
  #   receiver:
  #     - token_1
  #     - token_2
  uri: https://your-domain/message

Worktool:
  # 一个第三方的微信及企微机器人，具体信息可见 https://worktool.apifox.cn/
  # 无需更改默认的 uri 配置，需要填写你的 robot_id
  # 
  # 在 job.yaml 中的使用方法：
  # notifier:
  #   type: Worktool
  #   receiver:
  #     - 杰哥
  #     - 产品测试群
  uri: https://api.worktool.ymdyes.cn/wework/sendRawMessage
  robot_id: your_robot_id
```

### job.yaml

每个`job`都必须显式配置所有字段，但是可以使用YAML语法中的锚点和别名，如文件中的第二个 `job` 所示。

```YAML
x-render-config: &render-cfg
  width: 792
  filetype: png
  
jobs:
  - name: example-job          # 人类可读命名，没有其他用途
    page:
      # dashboard_uid 可以在 仪表盘设置-JSON模型 末尾可以看到。
      dashboard_uid: xxxxxxx
      # panel_uid 在进入单个面板后，页面链接的 viewPanel 参数可以看到。
      # 如果将 panel_uid 留空，则表示渲染整个仪表盘。
      panel_uid: 
      # 页面的查询参数，可以访问页面后直接复制。请不要重复设置 viewPanel，
      # 如果留空，则默认会添加 kiosk 以便于全屏显示
      # 如果设置了查询参数，则需要自行添加 kiosk
      query: var-subject=testteam&kiosk
    render:
      # 设置页面宽度，将会影响 png 和 pdf 的宽度。
      # 默认值 792 大约为 A4 纸宽度。
      # 高度将会根据页面的仪表盘自动计算，暂不支持显式配置。
      width: 792
      # 可选 png pdf csv xlsx，其中 csv xlsx 仅支持单个面板，不支持仪表
      # 盘导出 csv 和 xlsx 数据。此数据与前端面板：检查-数据-导出 csv 下
      # 载的数据一致。
      filetype: png       
    crontab: 0 0 * * *    # crontab 表达式，可自行了解
    notifier:
      # 使用的发送器类型，必须在 notifier.yaml 中配置
      type: Worktool
      # 报告接收者，即使只有一个接收者也必须设置为列表。
      # 不同的发送器的 receiver 意义不同，可参考 notifier.yaml 中的说明。
      receiver:
        - 杰哥
        - 产品测试群
```

