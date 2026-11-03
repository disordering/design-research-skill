const authorLabels = {human: '人工补记', ai_simulation: 'AI 模拟补记'};
const severityLabels = {critical: '严重', high: '高', medium: '中', low: '低'};

export function isReviewerFinding(issue) {
  return issue.origin === 'reviewer_finding';
}

export function reviewerLabel(issue) {
  return authorLabels[issue.authorType];
}

export function createReviewerFinding(fields, review) {
  const title = fields.title.trim();
  const steps = fields.steps.trim();
  const evidence = fields.evidence.trim();
  if (!title || !steps || !evidence) throw Error('请填写问题标题、复现步骤和证据位置。');
  if (!Object.hasOwn(authorLabels, fields.authorType)) throw Error('请选择记录来源。');
  if (!Object.hasOwn(severityLabels, fields.severity)) throw Error('请选择严重度。');
  return {
    id: 'note-' + crypto.randomUUID(),
    origin: 'reviewer_finding', authorType: fields.authorType,
    observedVersion: review.version, title, steps, evidence: {description: evidence},
    severity: fields.severity, originalSeverity: fields.severity,
    reviewStatus: 'pending', decision: 'candidate_issue', note: ''
  };
}

// 普通反馈保留在操作记录中。只有明确保存的问题才会进入报告正文。
export function reviewerMarkdown(issue) {
  const plain = value => String(value).replace(/[&<>]/g, char => ({'&':'&amp;', '<':'&lt;', '>':'&gt;'}[char]))
    .replace(/([\\`*_{}\[\]#!|])/g, '\\$1').replace(/\r?\n/g, '\n  ');
  const changed = issue.severity !== issue.originalSeverity ? '（原值：' + severityLabels[issue.originalSeverity] + '）' : '';
  return [
    '## ' + plain(issue.title),
    '- 记录来源：' + reviewerLabel(issue),
    '- 首次记录版本：v' + issue.observedVersion,
    '- 严重度：' + severityLabels[issue.severity] + changed,
    '- 复现步骤：' + plain(issue.steps),
    '- 证据：' + plain(issue.evidence.description),
    '- 审核状态：' + ({pending:'待审核', confirmed:'已确认', rejected:'已驳回', verify:'待验证'}[issue.reviewStatus]),
    '- 审核理由：' + plain(issue.note || '未填写'), ''
  ];
}
