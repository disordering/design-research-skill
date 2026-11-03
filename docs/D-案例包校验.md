# D 归档｜护法与吴山石案例包校验

2026-11-04。两份压缩包均含原交付清单和清单列出的 13 个文件。解压后可直接打开 `annotated-copy.png` 看设计画板，打开 `report-frame.png` 看报告图，打开 `report-final.md` 读 B 的评审结论。D 的裁决另外记在案例复核表中。

| 案例 | 清单 SHA-256 一致 | 标注画板 | 报告图 | 仓库原交付报告 |
| --- | --- | --- | --- | --- |
| 护法 | 13 / 13 | 2600 × 1693，补回 25 个字节 | 1080 × 910，补回 2 个字节 | [护法原报告](../deliverables/2026-11-02-hufa-review/report-final.md) |
| 吴山石 | 13 / 13 | 618 × 2400，补回 7 个字节 | 1080 × 1002，补回 3 个字节 | [吴山石原报告](../deliverables/2026-11-02-wushanshi-review/report-final.md) |

原仓库把交付目录中的文件按文本管理，将 CRLF 转成 LF。对文本恢复行尾，对每幅 PNG 则依据分块长度找出缺失字节数，在换行符前试补 CR，并逐块比对原始 CRC。最后从 ZIP 再读出文件，以原清单的 SHA-256 核验全包。护法 240 + 23 个 PNG 数据块、吴山石 115 + 32 个均通过 CRC，四图均已实际解码。还原后的两份 ZIP 和逐文件的 `校验结果.json` 保存在本地输出目录，下方命令可重新生成。[护法原清单](../deliverables/2026-11-02-hufa-review/SHA256SUMS.txt) · [吴山石原清单](../deliverables/2026-11-02-wushanshi-review/SHA256SUMS.txt)

如需重新生成，在仓库根目录运行以下命令，脚本只使用 Python 标准库。输出目录可自行指定。[还原与打包脚本](../scripts/d_restore_case_packages.py)

```powershell
python scripts/d_restore_case_packages.py "../outputs/D-新版案例证据包"
```
