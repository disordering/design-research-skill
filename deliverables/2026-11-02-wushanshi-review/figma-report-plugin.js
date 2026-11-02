const plan = {"source_root_node_id":"173:7654","source_title":"吴山石回收 · 交互案","report_name":"吴山石回收 · 交互案 · AI评审报告","title":"吴山石回收 · 交互案 · AI评审报告","subtitle":"基于完整交互流程与逐屏技术审查","summary":{"checks_total":48,"executed":16,"design_met":0,"candidate_issues":1,"screen_candidate_issues":7,"insufficient_evidence":15,"screen_reviews":7,"screen_complete":7,"screen_partial":0,"screen_ui_elements":172,"screen_ocr_blocks":239},"screen_summary":[{"node_id":"173:7668","page_type":"背包-道具详情界面（吴山石回收/分解交互）","status":"completed","ui_element_count":30,"ocr_block_count":20,"issue_count":2},{"node_id":"173:7674","page_type":"game_decompose_material_selection","status":"completed","ui_element_count":28,"ocr_block_count":0,"issue_count":3},{"node_id":"173:7676","page_type":"游戏内材料分解（吴山石回收）功能界面","status":"completed","ui_element_count":24,"ocr_block_count":48,"issue_count":3},{"node_id":"173:7675","page_type":"item_decompose_selection","status":"completed","ui_element_count":21,"ocr_block_count":48,"issue_count":3},{"node_id":"173:7677","page_type":"吴山石分解/回收选择确认界面","status":"completed","ui_element_count":23,"ocr_block_count":43,"issue_count":3},{"node_id":"173:7679","page_type":"item_decompose_selection","status":"completed","ui_element_count":22,"ocr_block_count":46,"issue_count":3},{"node_id":"173:7680","page_type":"积分商店-吴山石兑换详情","status":"completed","ui_element_count":24,"ocr_block_count":34,"issue_count":3}],"gaps":[{"text":"请提供策划案图3数值表，至少包含各等级分解可得积分、11~15级兑换价格、折损比例、单次分解/兑换数量上限和积分上限。当前材料只有“存在折损”和占位数值，无法核对积分获取、兑换扣减和经济折损。"},{"text":"15级是否允许分解和兑换？策划案同时出现“15级以上不可直接分解和兑换”“最高不超过15级”“可兑换11~15级”三种表述，需要确认15级边界口径；这会影响REQ4、REQ5、REQ7及分解/商店列表的覆盖核对。"},{"text":"交互案是否定义筛选记忆的账号或角色范围、重置条件，以及分解/兑换失败、背包满、积分上限或断网等异常恢复？当前材料未明确，会影响REQ8、E04、E05以及R21-R23的异常分支核对。"}],"annotations":[{"kind":"issue","scope":"screen+global","target_node_id":"173:7679","target_name":"image 1066","target_x":63.0,"target_y":3876.0,"target_width":1062.0,"target_height":600.0,"title":"选择、筛选与批量操作共用同一控件语义","detail":"多个界面把全选、绑定筛选和等级单选表达成相同空心圆，用户无法预判操作会替换、累加还是仅过滤当前选择。","action":"统一选择控件语言：复选框用于多选，单选圆点用于互斥选择，筛选器使用独立标签或开关，并在状态变化后显示作用范围。","heuristic_ids":["H06","H04","H02"],"severity":"high","color":"#C62828","bbox_hint":{"x":0.1,"y":0.855,"width":0.155,"height":0.065}},{"kind":"issue","scope":"screen","target_node_id":"173:7676","target_name":"image 1076","target_x":63.0,"target_y":1986.0,"target_width":1062.0,"target_height":600.0,"title":"选择状态与数量、结果汇总不一致","detail":"界面已出现勾选或全选状态，但数量仍显示 0000000，分解/兑换结果未同步，主按钮也保持可执行外观，用户无法在提交前核对。","action":"让选择状态驱动数量和结果汇总；数量为 0 或尚未计算时禁用主操作，并在同一状态下呈现明确的反馈。","heuristic_ids":["H05","H06","H04","H02"],"severity":"high","color":"#C62828","bbox_hint":{"x":0.6,"y":0.645,"width":0.25,"height":0.17}},{"kind":"issue","scope":"screen","target_node_id":"173:7680","target_name":"image 1069","target_x":63.0,"target_y":5470.0,"target_width":1062.0,"target_height":600.0,"title":"左列选中15级吴山石，右侧详情却是12级吴山石","detail":"左侧列表中『15级吴山石』带有高亮边框，是最像当前选中项的条目；但右栏详情标题、等级lv.57与下方数量/总价/兑换全部属于『12级吴山石』。玩家据此无法确认自己正在兑换哪一个等级的材料，在高价值回收/兑换场景中很容易按错误的等级下单，且没有任何提示说明高亮与详情为何不一致。","action":"让详情标题与左侧唯一选中项由同一状态驱动：选中哪一条，详情标题、图标、总价即同步为该等级；若列表允许『浏览但与已选不同』，必须在详情标题处明确标注『当前选中：xx级』并在卡片上使用统一选中样式，避免…","heuristic_ids":["H06"],"severity":"high","color":"#C62828","bbox_hint":{"x":0.117,"y":0.108,"width":0.64,"height":0.055}},{"kind":"issue","scope":"screen","target_node_id":"173:7674","target_name":"image 35","target_x":63.0,"target_y":1353.0,"target_width":1062.0,"target_height":600.0,"title":"数量与相邻数值的位数、占位格式不一致","detail":"数量字段以七位前导零显示，而相邻结果和拥有量使用九位数字；字段容量与展示格式不能稳定承载同类数值。","action":"按最长可见数值统一字段宽度、对齐与占位规则，避免用前导零混同真实零值和未计算状态。","heuristic_ids":["H05","H04"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.7358,"y":0.6608,"width":0.1,"height":0.055}},{"kind":"issue","scope":"screen","target_node_id":"173:7680","target_name":"image 1069","target_x":63.0,"target_y":5470.0,"target_width":1062.0,"target_height":600.0,"title":"右缘竖排页签选中态几乎不可辨，无法确认当前所在模块","detail":"『积分商店』与『分解』是玩家在回收与兑换两条路径间切换的唯一入口，但两者文字都几乎与深色底融合，选中项也没有可读的高亮/指示差异。玩家难以确认自己此刻在哪个模块，也难以发现『分解』这条回收路径的存在，削弱了本方案“提供可实际使用的回收渠道”的入口可见性。","action":"提高两个页签文字的对比度，并为选中项提供明确且稳定的选中标记（如高亮底、指示条或加粗），使当前模块在不依赖记忆的情况下可辨认。","heuristic_ids":["H01"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.888,"y":0.18,"width":0.071,"height":0.52}},{"kind":"issue","scope":"screen","target_node_id":"173:7668","target_name":"image 1063","target_x":63.0,"target_y":555.0,"target_width":1062.0,"target_height":566.0,"title":"同屏两个「回收」与「分解」并列，动作语义与作用域不明","detail":"屏内出现三处回收语义入口：顶部操作区「回收」（0.715,0.11）与「整理」并列，详情操作列中「分解」（0.37,0.589）与「回收」（0.37,0.682）上下相邻。三者没有任何文字说明作用范围（整包批处理 / 当前道具）与产出差别。用户点击顶部「回收」可能进入批量入口而…","action":"为两个「回收」补充作用域说明（如顶部改为「批量回收」、详情列改为「回收此道具」），并统一分解与回收的命名规则，使同一动作只有一个名称、不同动作有可辨识名称。","heuristic_ids":["H04"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.36,"y":0.58,"width":0.1,"height":0.18}},{"kind":"issue","scope":"screen","target_node_id":"173:7668","target_name":"image 1063","target_x":63.0,"target_y":555.0,"target_width":1062.0,"target_height":566.0,"title":"当前道具名称对比度低于副标题，选中对象身份不易辨认","detail":"确认「我现在选中的是谁」依赖详情面板头部的主名称，但主名「1级吴山石」（bbox 0.133,0.365,0.11,0.045）以 0.2471 的局部对比呈现，比其下属的辅助文字「吴山石」（0.5412）更暗，形成层级倒置；右侧网格中对应格仅有细白描边（E24，0.752,0…","action":"提升道具主名亮度/字号，使其成为详情面板中最强的文字层级，副标题降级；同时加粗网格选中描边或增加选中角标，使选中格与详情主名一一对应。","heuristic_ids":["H06"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.133,"y":0.365,"width":0.11,"height":0.045}}],"heuristic_summary":{"H01":1,"H02":2,"H04":4,"H05":2,"H06":4},"colors":{"issue":"#C62828","gap":"#9A6700","review":"#0B63CE","pass":"#18794E","report_bg":"#F6F8FB","panel_bg":"#FFFFFF","text":"#172033","muted":"#56637A","border":"#C9D2E0"},"session_id":"session-b111276e8fa64c9d8417b3c6e6487f69","run_id":"run-670ae0bc795f465ba57edec80e1711b0"};
const reportFonts = {
  regular: { family: "Noto Sans SC", style: "Regular" },
  medium: { family: "Noto Sans SC", style: "Medium" },
  bold: { family: "Noto Sans SC", style: "Bold" }
};
await Promise.all(Object.values(reportFonts).map(font => figma.loadFontAsync(font)));

const original = await figma.getNodeByIdAsync(plan.source_root_node_id);
if (!original || original.type !== "FRAME") throw new Error("Source interaction frame not found");
const page = original.parent;
if (!page || page.type !== "PAGE") throw new Error("Source frame must be on a page");
await figma.setCurrentPageAsync(page);

const duplicateName = `${plan.source_title} · AI审查标注副本`;
const reuseWrapper = page.findOne(n =>
  n.type === "FRAME" &&
  n.name.includes(plan.source_title) &&
  n.name.includes("AI审查标注稿")
);
let duplicate = reuseWrapper
  ? reuseWrapper.findOne(n => n.name.includes("AI审查标注副本"))
  : page.findOne(n => n.name === duplicateName);
if (!duplicate) {
  duplicate = original.clone();
  duplicate.name = duplicateName;
  duplicate.x = original.x + original.width + 320;
  duplicate.y = original.y;
  page.appendChild(duplicate);
}
if (duplicate.type !== "FRAME") throw new Error("Annotated copy must be a frame");
if (duplicate.layoutMode !== "NONE") {
  duplicate.primaryAxisSizingMode = "FIXED";
  duplicate.counterAxisSizingMode = "FIXED";
}
duplicate.resize(original.width, original.height);
const reviewWrapper = duplicate.parent && duplicate.parent.type === "FRAME"
  ? duplicate.parent : null;
const reviewBounds = duplicate.absoluteBoundingBox || {
  x: duplicate.x,
  y: duplicate.y,
  width: duplicate.width,
  height: duplicate.height
};
const wrapperBounds = reviewWrapper && reviewWrapper.absoluteBoundingBox
  ? reviewWrapper.absoluteBoundingBox
  : { x: reviewBounds.x, y: reviewBounds.y, width: reviewBounds.width, height: reviewBounds.height };

const oldPanel = page.findOne(n => n.name === "交互案 · AI审查说明栏");
if (oldPanel) oldPanel.remove();
const oldLayer = reviewWrapper
  ? reviewWrapper.findOne(n => n.name.includes("AI彩色标注层"))
  : null;
if (oldLayer) oldLayer.remove();
const annotationPrefix = `AI审查批注 · ${plan.source_title} · `;
for (const child of [...duplicate.children]) {
  if (child.name.startsWith(annotationPrefix)) child.remove();
}
for (const child of [...page.children]) {
  if (child.name.startsWith(annotationPrefix)) child.remove();
}

function rgba(hex, opacity = 1) {
  const clean = hex.replace("#", "");
  return {
    type: "SOLID",
    color: {
      r: parseInt(clean.slice(0, 2), 16) / 255,
      g: parseInt(clean.slice(2, 4), 16) / 255,
      b: parseInt(clean.slice(4, 6), 16) / 255
    },
    opacity
  };
}

function addText(parent, content, font, size, color, width) {
  const node = figma.createText();
  node.fontName = font;
  node.fontSize = size;
  node.fills = [rgba(color)];
  node.characters = content;
  node.resize(width, node.height);
  node.textAutoResize = "HEIGHT";
  parent.appendChild(node);
  node.layoutSizingHorizontal = "FILL";
  return node;
}

function shortText(value, limit = 220) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > limit ? text.slice(0, limit - 1) + "…" : text;
}

const occupiedNotes = [];
function overlaps(first, second) {
  return !(
    first.x + first.width <= second.x ||
    second.x + second.width <= first.x ||
    first.y + first.height <= second.y ||
    second.y + second.height <= first.y
  );
}
const numberedNodes = duplicate.findAll(node =>
  node.type === "TEXT" &&
  node.visible &&
  /^\s*\d+[.、]/.test(node.characters || "")
);
function nearestNumbered(highlightAbs) {
  let best = null;
  let bestDistance = Infinity;
  const hx = highlightAbs.x + highlightAbs.width / 2;
  const hy = highlightAbs.y + highlightAbs.height / 2;
  for (const node of numberedNodes) {
    const box = node.absoluteBoundingBox;
    if (!box) continue;
    const nx = box.x + box.width / 2;
    const ny = box.y + box.height / 2;
    const distance = Math.hypot(nx - hx, ny - hy);
    if (distance < bestDistance) {
      bestDistance = distance;
      best = { node, box };
    }
  }
  return best;
}
const annotationNodeIds = [];
for (let index = 0; index < plan.annotations.length; index++) {
  const annotation = plan.annotations[index];
  const target = {
    x: annotation.target_x,
    y: annotation.target_y,
    width: annotation.target_width,
    height: annotation.target_height
  };
  let highlight = target;
  if (annotation.bbox_hint) {
    highlight = {
      x: target.x + target.width * Number(annotation.bbox_hint.x || 0),
      y: target.y + target.height * Number(annotation.bbox_hint.y || 0),
      width: Math.max(18, target.width * Number(annotation.bbox_hint.width || 0)),
      height: Math.max(18, target.height * Number(annotation.bbox_hint.height || 0))
    };
  }
  const outline = figma.createRectangle();
  outline.name = `${annotationPrefix}目标框 ${index + 1} · ${annotation.title}`;
  outline.x = reviewBounds.x + highlight.x;
  outline.y = reviewBounds.y + highlight.y;
  outline.resize(highlight.width, highlight.height);
  outline.fills = [rgba(annotation.color, 0.05)];
  outline.strokes = [rgba(annotation.color)];
  outline.strokeWeight = 4;
  outline.strokeAlign = "INSIDE";
  page.appendChild(outline);
  annotationNodeIds.push(outline.id);

  const highlightAbs = {
    x: reviewBounds.x + highlight.x,
    y: reviewBounds.y + highlight.y,
    width: highlight.width,
    height: highlight.height
  };
  const nearest = nearestNumbered(highlightAbs);
  const anchorBox = nearest ? nearest.box : highlightAbs;
  let noteX = anchorBox.x;
  let noteY = anchorBox.y + anchorBox.height + 8;
  const noteWidth = 360;
  if (noteX + noteWidth > reviewBounds.x + reviewBounds.width - 20) {
    noteX = Math.max(
      reviewBounds.x + 20,
      reviewBounds.x + reviewBounds.width - noteWidth - 20
    );
  }
  const noteBg = figma.createRectangle();
  noteBg.name = `${annotationPrefix}底色 ${index + 1} · ${annotation.title}`;
  noteBg.cornerRadius = 8;
  noteBg.fills = [rgba(plan.colors.panel_bg, 0.96)];
  noteBg.strokes = [rgba(annotation.color)];
  noteBg.strokeWeight = 2;
  noteBg.strokeAlign = "INSIDE";
  page.appendChild(noteBg);
  annotationNodeIds.push(noteBg.id);
  const header = figma.createText();
  header.name = `${annotationPrefix}标题 ${index + 1} · ${annotation.title}`;
  header.fontName = reportFonts.bold;
  header.fontSize = 18;
  header.fills = [rgba(annotation.color)];
  header.characters = `AI${String(index + 1).padStart(2, "0")} · ${annotation.heuristic_ids.join("/") || "无判据"}`;
  header.resize(noteWidth, header.height);
  header.textAutoResize = "HEIGHT";
  page.appendChild(header);
  annotationNodeIds.push(header.id);

  const body = figma.createText();
  body.name = `${annotationPrefix}正文 ${index + 1} · ${annotation.title}`;
  body.fontName = reportFonts.medium;
  body.fontSize = 15;
  body.fills = [rgba(plan.colors.text)];
  body.characters = `${annotation.title}
${annotation.detail}`;
  body.resize(noteWidth, body.height);
  body.textAutoResize = "HEIGHT";
  page.appendChild(body);
  annotationNodeIds.push(body.id);

  const action = figma.createText();
  action.name = `${annotationPrefix}建议 ${index + 1} · ${annotation.title}`;
  action.fontName = reportFonts.regular;
  action.fontSize = 13;
  action.fills = [rgba(plan.colors.muted)];
  action.characters = `建议：${shortText(annotation.action, 120)}`;
  action.resize(noteWidth, action.height);
  action.textAutoResize = "HEIGHT";
  page.appendChild(action);
  annotationNodeIds.push(action.id);

  const noteHeight = header.height + body.height + action.height + 18;
  for (let attempt = 0; attempt < 30; attempt++) {
    const box = { x: noteX, y: noteY, width: noteWidth, height: noteHeight };
    const hit = occupiedNotes.find(item => overlaps(item, box));
    if (!hit) break;
    noteY = hit.y + hit.height + 12;
  }
  if (noteY + noteHeight > reviewBounds.y + reviewBounds.height - 20) {
    noteY = Math.max(
      reviewBounds.y + 20,
      reviewBounds.y + reviewBounds.height - noteHeight - 20
    );
  }
  noteBg.x = noteX - 8;
  noteBg.y = noteY - 8;
  noteBg.resize(noteWidth + 16, noteHeight + 12);
  header.x = noteX;
  header.y = noteY;
  body.x = noteX;
  body.y = noteY + header.height + 4;
  action.x = noteX;
  action.y = body.y + body.height + 4;
  occupiedNotes.push({ x: noteX, y: noteY, width: noteWidth, height: noteHeight });
}

const existingReport = page.findOne(n => n.name === plan.report_name);
if (existingReport) existingReport.remove();

const report = figma.createAutoLayout("VERTICAL", {
  name: plan.report_name,
  itemSpacing: 22
});
report.resize(1080, 100);
report.paddingTop = 44;
report.paddingBottom = 44;
report.paddingLeft = 44;
report.paddingRight = 44;
report.cornerRadius = 24;
report.fills = [rgba(plan.colors.report_bg)];
report.strokes = [rgba(plan.colors.border)];
report.strokeWeight = 2;
report.x = reviewBounds.x;
report.y = wrapperBounds.y + wrapperBounds.height + 420;

function section(title, accent) {
  const frame = figma.createAutoLayout("VERTICAL", { name: title, itemSpacing: 14 });
  frame.paddingTop = 22;
  frame.paddingBottom = 22;
  frame.paddingLeft = 24;
  frame.paddingRight = 24;
  frame.cornerRadius = 12;
  frame.fills = [rgba(plan.colors.panel_bg)];
  frame.strokes = [rgba(accent, 0.8)];
  frame.strokeWeight = 2;
  report.appendChild(frame);
  frame.layoutSizingHorizontal = "FILL";
  addText(frame, title, reportFonts.bold, 24, accent, 980);
  return frame;
}

addText(report, plan.title, reportFonts.bold, 42, plan.colors.text, 980);
addText(report, plan.subtitle, reportFonts.regular, 18, plan.colors.muted, 980);
addText(
  report,
  `评审完成 · 检查 ${plan.summary.executed}/${plan.summary.checks_total} · 跨项发现 ${plan.summary.candidate_issues} · 系统性问题 ${plan.summary.screen_candidate_issues} · 证据不足 ${plan.summary.insufficient_evidence}`,
  reportFonts.medium, 18, plan.colors.review, 980
);

const overview = section("01 · 评审摘要", plan.colors.review);
addText(
  overview,
  `逐屏技术审查 ${plan.summary.screen_reviews} 个完整界面，其中完整完成 ${plan.summary.screen_complete} 个、部分完成 ${plan.summary.screen_partial} 个；累计识别 UI 元素 ${plan.summary.screen_ui_elements} 个、OCR 文本块 ${plan.summary.screen_ocr_blocks} 个。`,
  reportFonts.regular, 17, plan.colors.text, 980
);
addText(
  overview,
  "完整完成表示 OCR、元素、统计和屏内规则审查均已产出；部分完成会保留具体限制，不把空元素结果当作通过。",
  reportFonts.regular, 15, plan.colors.muted, 980
);
const heuristicRows = Object.entries(plan.heuristic_summary || {});
addText(
  overview,
  heuristicRows.length
    ? `命中启发式维度：${heuristicRows.map(([id, count]) => `${id} × ${count}`).join(" · ")}`
    : "本轮候选问题未绑定可识别的启发式维度，不能把流程缺项冒充交互结论。",
  reportFonts.regular, 16, plan.colors.text, 980
);

const findingsSection = section("02 · 候选问题", plan.colors.issue);
for (let i = 0; i < plan.annotations.length; i++) {
  const item = plan.annotations[i];
  addText(findingsSection, `F${String(i + 1).padStart(3, "0")} · ${item.title}`, reportFonts.bold, 20, plan.colors.issue, 940);
  addText(findingsSection, shortText(item.detail, 360), reportFonts.regular, 16, plan.colors.text, 940);
  addText(findingsSection, `建议：${shortText(item.action, 220)}`, reportFonts.medium, 15, plan.colors.muted, 940);
}

const screensSection = section("03 · 逐屏技术审查", plan.colors.review);
for (const screen of plan.screen_summary) {
  addText(
    screensSection,
    `${screen.page_type || screen.node_id} · ${screen.status === "completed" ? "完整完成" : "部分完成"} · UI ${screen.ui_element_count} · OCR ${screen.ocr_block_count} · 屏内问题 ${screen.issue_count}`,
    reportFonts.regular, 16, screen.status === "completed" ? plan.colors.text : plan.colors.gap, 940
  );
}

const gapsSection = section("04 · 待补证据与业务确认", plan.colors.gap);
for (let i = 0; i < plan.gaps.length; i++) {
  addText(
    gapsSection,
    `G${String(i + 1).padStart(2, "0")} · ${shortText(plan.gaps[i].text, 300)}`,
    reportFonts.regular, 16, plan.colors.text, 940
  );
}

const legendSection = section("05 · 标注说明", plan.colors.pass);
addText(legendSection, "红色：副本编号、目标框与系统性问题；黄色与青色：仅用于报告中的证据缺口和审查统计。", reportFonts.regular, 16, plan.colors.text, 940);
addText(legendSection, "标注位于原交互案的独立副本上，原稿未修改。", reportFonts.medium, 16, plan.colors.pass, 940);
addText(legendSection, `会话：${plan.session_id} · 运行：${plan.run_id}`, reportFonts.regular, 13, plan.colors.muted, 940);

return {
  success: true,
  reportId: report.id,
  duplicateId: duplicate.id,
  annotationCount: plan.annotations.length,
  reportBounds: { x: report.x, y: report.y, width: report.width, height: report.height },
  createdNodeIds: [report.id, ...annotationNodeIds]
};
