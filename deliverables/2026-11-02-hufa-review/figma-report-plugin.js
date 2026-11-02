const plan = {"source_root_node_id":"173:6083","source_title":"护法｜交互稿","report_name":"护法｜交互稿 · AI评审报告","title":"护法｜交互稿 · AI评审报告","subtitle":"基于完整交互流程与逐屏技术审查","summary":{"checks_total":49,"executed":16,"design_met":0,"candidate_issues":0,"screen_candidate_issues":6,"insufficient_evidence":16,"screen_reviews":8,"screen_complete":8,"screen_partial":0,"screen_ui_elements":204,"screen_ocr_blocks":290},"screen_summary":[{"node_id":"173:7204","page_type":"RPG 角色养成/升星界面（衍灵护法系统）","status":"completed","ui_element_count":20,"ocr_block_count":24,"issue_count":3},{"node_id":"173:6094","page_type":"仙侠手游主城界面（护法/衍灵系统入口浮层）","status":"completed","ui_element_count":40,"ocr_block_count":51,"issue_count":2},{"node_id":"173:7229","page_type":"角色养成/护法详情界面（静态交互稿）","status":"completed","ui_element_count":18,"ocr_block_count":28,"issue_count":3},{"node_id":"173:6361","page_type":"character_star_upgrade_detail","status":"completed","ui_element_count":24,"ocr_block_count":37,"issue_count":2},{"node_id":"173:6135","page_type":"护法养成/升阶升星界面","status":"completed","ui_element_count":34,"ocr_block_count":47,"issue_count":3},{"node_id":"173:6760","page_type":"character_detail_formation","status":"completed","ui_element_count":26,"ocr_block_count":37,"issue_count":4},{"node_id":"173:6956","page_type":"护法养成/强化详情界面（织羽）","status":"completed","ui_element_count":14,"ocr_block_count":31,"issue_count":4},{"node_id":"173:6582","page_type":"character_upgrade_detail","status":"completed","ui_element_count":28,"ocr_block_count":35,"issue_count":2}],"gaps":[{"text":"护法系统面向的目标玩家范围（新手、回流或全体养成用户）及“扩展玩家养成体验”的成功指标或验收阈值是什么？"},{"text":"策划文档引用的框架脑图（原文配图01）与UX流程图（原文配图29）是否有可查看的图像或对应 Figma 节点？"},{"text":"战斗上阵3护法、衍灵重塑返还、红点/呼吸特效、多队伍上阵校验等未出现在现有9屏中的设计稿或运行记录是否可补充？"}],"annotations":[{"kind":"issue","scope":"screen","target_node_id":"173:6956","target_name":"Slide 16:9 - 43","target_x":5256.0,"target_y":4934.0,"target_width":1920.0,"target_height":1080.0,"title":"'一键强化'的预期结果无法从邻近信息确定","detail":"玩家在按下主操作前无法判断会从45级升到几级、'+5' 与 '+500' 各自代表什么、会消耗多少碎片。强化属于不可逆的资源消耗，结果口径不明会直接导致误操作与后悔。","action":"在按钮上方用一行口径统一的预览表达结果与消耗，例如'45级 → 50级'、'经验 +500/120'、'消耗碎片 ×N'，并保证数值带单位、彼此不冲突。","heuristic_ids":["H02"],"severity":"high","color":"#C62828","bbox_hint":{"x":0.25,"y":0.8,"width":0.63,"height":0.13}},{"kind":"issue","scope":"screen","target_node_id":"173:6135","target_name":"Slide 16:9 - 37","target_x":10442.0,"target_y":162.0,"target_width":1920.0,"target_height":1080.0,"title":"选中“升阶”页签，主操作却是“升星”","detail":"当前激活的页签与其右侧信息区表达的是“升阶”（等级 +13 提升至 +14、天赋激活条件），但唯一的主操作按钮命名为“升星”，且“升星”页签处于未选中的暗态。用户在已投入升阶判断的情况下，无法确定按下该按钮执行的是升星还是升阶，属于状态与动作含义冲突，存在误用养成材料、误跳转页…","action":"使主按钮名称与当前激活页签一致（升阶态显示“升阶/提升”，升星态显示“升星”），或明确将“升星”按钮限定归入升星页签内容区，避免同一按钮在两个语义下通用。","heuristic_ids":["H02","H04"],"severity":"high","color":"#C62828","bbox_hint":{"x":0.794,"y":0.911,"width":0.094,"height":0.056}},{"kind":"issue","scope":"screen","target_node_id":"173:6135","target_name":"Slide 16:9 - 37","target_x":10442.0,"target_y":162.0,"target_width":1920.0,"target_height":1080.0,"title":"属性提升行的名称与数值几乎不可读","detail":"同一右侧面板中，栏目标题与说明文字清晰可读，而决定“是否升阶”的三行属性名与数值被压到接近背景亮度（第三行 0.0392），文字与底色几乎融合。用户在提交升阶前无法核对本次提升的具体属性与数值，只能凭感觉点按钮，削弱了消耗性操作的决策依据。","action":"将属性行文字提升至与同面板说明文字一致的对比度层级（如提高字色亮度或加深行背板），并保证三行使用统一的文字与数值对比规则，去掉覆盖在文字上的装饰渐变光效。","heuristic_ids":["H06","H08","H04","H02"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.681,"y":0.3,"width":0.256,"height":0.145}},{"kind":"issue","scope":"screen","target_node_id":"173:6094","target_name":"Slide 16:9 - 36","target_x":2489.0,"target_y":144.0,"target_width":1920.0,"target_height":1080.0,"title":"高亮数字徽章缺少语义和目标锚点","detail":"黄色数字“1”没有说明计数对象、步骤含义或指向入口，并与既有红点提示争夺注意力。","action":"为提示补充明确标签或箭头锚点，并统一新内容、数量、步骤和可解锁状态等不同提示语义。","heuristic_ids":["H08","H06","H04"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.442,"y":0.55,"width":0.06,"height":0.09}},{"kind":"issue","scope":"screen","target_node_id":"173:7229","target_name":"Slide 16:9 - 44","target_x":5226.0,"target_y":144.0,"target_width":1920.0,"target_height":1080.0,"title":"角色或护法列表缺少可辨认的当前选中态","detail":"左侧列表承载角色切换，但没有稳定高亮或勾选，用户无法把当前详情与列表对象一一对应。","action":"为当前对象提供持续可见的选中态，并让详情标题、头像和主操作对象由同一选择状态驱动。","heuristic_ids":["H06","H08"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.008,"y":0.092,"width":0.438,"height":0.812}},{"kind":"issue","scope":"screen","target_node_id":"173:6361","target_name":"Slide 16:9 - 38","target_x":8101.5,"target_y":162.0,"target_width":1920.0,"target_height":1080.0,"title":"升星主按钮与中央同名圆钮的视觉权重倒挂，主操作不易定位","detail":"页面中央的『护法升星』圆钮更大、更亮、更饱和，视觉上像主操作；而真正消耗材料执行升星的按钮『升星』缩在右下角（0.753–0.861, 0.913–0.971），面积只有中央圆钮的一半左右，且与中央圆钮名称高度相似。用户视线先被中央圆钮吸引，容易误点或被引到错误入口，需要额外辨…","action":"把提交按钮做成明确的动作带：加大按钮面积与填充对比、与上方材料卡连成『成本＋执行』整体；中央圆钮改为纯状态展示或独立入口，并加副标题（如『升星进度/入口』）以与右下『升星』动作按钮区分。","heuristic_ids":["H08"],"severity":"medium","color":"#C62828","bbox_hint":{"x":0.753,"y":0.913,"width":0.108,"height":0.058}}],"heuristic_summary":{"H02":3,"H04":3,"H06":3,"H08":4},"colors":{"issue":"#C62828","gap":"#9A6700","review":"#0B63CE","pass":"#18794E","report_bg":"#F6F8FB","panel_bg":"#FFFFFF","text":"#172033","muted":"#56637A","border":"#C9D2E0"},"session_id":"session-d6c6e2947166466d8e389839b708f635","run_id":"run-cfd954e4edf0411d96ca6e93f3274118"};
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
