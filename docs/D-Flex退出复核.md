# D-FX-001｜Flex 新增器材表单的两个退出入口

2026-11-04，Codex 在浏览器中操作[仓库指定的 Flex 原型](https://www.figma.com/proto/afbY0l8lwBqAKKQr84YKl4/Flex-Gym-Inventory-App?node-id=2312-5527&starting-point-node-id=1491%3A3094&scaling=scale-down&content-scaling=fixed)。任务是从愿望清单打开新增表单，再放弃这次新增。

**D 结论：确认原型的局部退出问题。** 在空白 Add Item 表单，从首页进入的两轮中，底部 Cancel、左上返回箭头均未离开当前画面。对照测试中，My Wishlist 页左上箭头能返回 Dashboard。原先“退出均失败”的说法范围过大；可复现的范围是**新增表单的这两个入口**。建议列为本原型走查的高优先修复项。玩家可以进入该分支，却不能用这两个明示入口完成放弃任务。运行产品与有输入内容时的草稿状态另测。

| 核验动作 | 操作前 → 操作后 | 结果 |
| --- | --- | --- |
| 首页点底部 Wishlist，清单点 Add Item | Dashboard（2312:5527）→ My Wishlist（2289:2407）→ Add Item（2289:2448） | 两轮均能进入 |
| 向下滚动至 Cancel 完整可见，点击按钮中心 | Add Item → Add Item | 两轮均停在同一节点，未出现确认框或返回清单 |
| 点 Add Item 标题左边的返回箭头 | Add Item → Add Item | 两轮均停在表单。第二轮调换次序，先点返回再点取消 |
| 点 My Wishlist 标题左边的返回箭头 | My Wishlist → Dashboard | 清单页的返回可用 |

**建议与验收：** 为 Add Item 的 Cancel 和标题返回分别连接愿望清单；空表单点任一入口应回到原空清单。若产品对已有输入另有草稿规则，先确定保留或放弃的要求，再测填写后的两条路径。验证时点应用内控件，单独记录控件中心、画面标题和节点编号。重新打开入口仅用于复位。

**操作证据：** [原始顺序、时刻、画面链接与截图文件名](D-复核证据/Flex/操作记录.json) · [滚动后两个按钮的位置](D-复核证据/Flex/05-取消完整可见.jpg) · [点击 Cancel 后](D-复核证据/Flex/06-取消后仍是表单.jpg) · [第二轮点击返回后](D-复核证据/Flex/12-再次点表单返回.jpg) · [清单返回成功的对照](D-复核证据/Flex/10-清单返回首页.jpg)。
