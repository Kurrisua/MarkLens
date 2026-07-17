import { useEffect, useMemo, useState, type ReactNode } from "react";
import { NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { motion, useReducedMotion } from "motion/react";
import {
  ArrowRight, BookOpenText, Briefcase, CaretLeft, ChartPolar, Check, CircleNotch,
  CloudArrowUp, Database, Eye, FileMagnifyingGlass, FileText, Gauge, House, Info,
  List, MagnifyingGlass, Moon, PencilSimple, Plus, Printer, Scales, ShieldCheck, Sun,
  UploadSimple, Warning, X
} from "@phosphor-icons/react";
import {
  Badge, Button, Callout, Card, Checkbox, Flex, Heading, Progress, Separator,
  Text, TextArea, TextField, Theme
} from "@radix-ui/themes";
import {
  PolarAngleAxis, PolarGrid, Radar, RadarChart, ResponsiveContainer, Tooltip as ChartTooltip
} from "recharts";
import { z } from "zod";

import { ApiError, api, assetUrl } from "./api";
import type {
  AgentRun, Citation, DocumentSection, RiskLevel, SourceDefinition, TrademarkEvidence
} from "./contracts";

type Appearance = "light" | "dark";

const navItems = [
  { to: "/", label: "工作台", icon: House, end: true },
  { to: "/new", label: "新建分析", icon: Plus },
  { to: "/consult", label: "法律咨询", icon: BookOpenText },
  { to: "/sources", label: "数据源", icon: Database }
];

function initialAppearance(): Appearance {
  const saved = localStorage.getItem("marklens-theme");
  if (saved === "light" || saved === "dark") return saved;
  return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function AppShell({ children, appearance, setAppearance }: {
  children: ReactNode; appearance: Appearance; setAppearance: (value: Appearance) => void;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="app-shell">
      <aside className={open ? "sidebar sidebar-open" : "sidebar"}>
        <div className="brand-row">
          <NavLink to="/" className="brand" onClick={() => setOpen(false)}>
            <span className="brand-symbol"><FileMagnifyingGlass size={23} weight="duotone" /></span>
            <span><strong>MarkLens</strong><small>可信商标工作台</small></span>
          </NavLink>
          <button className="sidebar-close" onClick={() => setOpen(false)} aria-label="关闭导航"><X size={20} /></button>
        </div>
        <nav className="primary-nav" aria-label="主导航">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              <Icon size={19} weight="duotone" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-boundary">
          <ShieldCheck size={19} weight="duotone" />
          <div><strong>教学风险初筛</strong><small>不替代官方检索或律师意见</small></div>
        </div>
        <div className="theme-switcher" aria-label="主题切换">
          <button className={appearance === "light" ? "selected" : ""} onClick={() => setAppearance("light")}><Sun size={16} />浅色</button>
          <button className={appearance === "dark" ? "selected" : ""} onClick={() => setAppearance("dark")}><Moon size={16} />深色</button>
        </div>
      </aside>
      <div className="content-column">
        <header className="mobile-header">
          <button onClick={() => setOpen(true)} aria-label="打开导航"><List size={22} /></button>
          <strong>MarkLens</strong>
          <button onClick={() => setAppearance(appearance === "light" ? "dark" : "light")} aria-label="切换主题">
            {appearance === "light" ? <Moon size={20} /> : <Sun size={20} />}
          </button>
        </header>
        <main className="main-content">{children}</main>
      </div>
      {open && <button className="nav-scrim" onClick={() => setOpen(false)} aria-label="关闭导航遮罩" />}
    </div>
  );
}

function PageHeader({ title, description, action, back }: { title: string; description: string; action?: ReactNode; back?: string }) {
  const navigate = useNavigate();
  return (
    <header className="page-header">
      <div className="title-row">
        {back && <button className="back-button" onClick={() => navigate(back)} aria-label="返回"><CaretLeft size={19} /></button>}
        <div><Heading as="h1" size="7">{title}</Heading><Text as="p" color="gray" size="3">{description}</Text></div>
      </div>
      {action}
    </header>
  );
}

function LoadingState({ label = "正在读取证据" }: { label?: string }) {
  return <div className="state-panel loading-state"><CircleNotch size={26} className="spin" /><strong>{label}</strong><span>请稍候，页面会自动更新。</span></div>;
}

function ErrorState({ error, action }: { error: unknown; action?: ReactNode }) {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="state-panel error-state"><Warning size={27} weight="duotone" /><strong>{apiError?.message ?? "暂时无法读取数据"}</strong>
      <span>{apiError?.requestId ? `请求编号：${apiError.requestId}` : "请确认 API 和 MySQL 已启动。"}</span>{action}
    </div>
  );
}

function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="state-panel"><FileMagnifyingGlass size={29} weight="duotone" /><strong>{title}</strong><span>{description}</span>{action}</div>;
}

function StatusBadge({ state }: { state: string }) {
  const color = state === "ready" || state === "completed" ? "green" : state === "unavailable" || state === "failed" ? "red" : "amber";
  const labels: Record<string, string> = { ready: "正常", degraded: "降级", unavailable: "不可用", completed: "已完成", failed: "失败", running: "运行中", queued: "排队中" };
  return <Badge color={color} variant="soft">{labels[state] ?? state}</Badge>;
}

function HomePage() {
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 30_000 });
  const dashboard = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboard });
  const navigate = useNavigate();
  return (
    <>
      <PageHeader title="商标证据工作台" description="从事实确认开始，沿检索、评分、法律依据和报告形成可追溯链路。"
        action={<Button size="3" onClick={() => navigate("/new")}><Plus size={17} />新建分析</Button>} />
      {health.isLoading ? <LoadingState label="正在检查系统依赖" /> : health.error ? <ErrorState error={health.error} /> : (
        <section className="dependency-strip" aria-label="系统依赖">
          {Object.entries(health.data!.dependencies).map(([key, value]) => (
            <div key={key}><span>{key === "mysql" ? "MySQL" : key === "deepseek" ? "DeepSeek" : "本地模型"}</span><StatusBadge state={value.status} /><small title={value.detail}>{value.detail}</small></div>
          ))}
        </section>
      )}
      {dashboard.isLoading ? <LoadingState label="正在读取工作台" /> : dashboard.error ? <ErrorState error={dashboard.error} /> : (
        <>
          <section className="metric-layout">
            <Card className="primary-metric"><div><Text color="gray">商标记录</Text><strong>{dashboard.data!.counts.trademarks.toLocaleString()}</strong><small>{dashboard.data!.data_version}</small></div><Database size={31} weight="duotone" /></Card>
            <div className="metric-pair">
              <div><span>法律资料</span><strong>{dashboard.data!.counts.legal_sources}</strong></div>
              <div><span>分析案件</span><strong>{dashboard.data!.counts.cases}</strong></div>
            </div>
            <Card className="law-version"><Scales size={26} weight="duotone" /><div><span>当前适用版本</span><strong>{dashboard.data!.legal_version}</strong><small>2027-01-01 前默认适用</small></div></Card>
          </section>
          <section className="home-grid">
            <div className="section-block">
              <div className="section-heading"><div><Heading size="4">最近案件</Heading><Text color="gray" size="2">继续查看已有事实快照</Text></div></div>
              {dashboard.data!.recent_cases.length ? <div className="recent-list">{dashboard.data!.recent_cases.map(item => (
                <button key={item.case_id} onClick={() => navigate(`/cases/${item.case_id}`)}>
                  <span className="case-monogram">{item.trademark_name.slice(0, 1)}</span><span><strong>{item.trademark_name}</strong><small>第 {item.nice_classes.join("、")} 类</small></span><ArrowRight size={17} />
                </button>
              ))}</div> : <EmptyState title="还没有案件" description="创建首个分析后，案件会保留在这里。" action={<Button onClick={() => navigate("/new")}>开始分析</Button>} />}
            </div>
            <aside className="workflow-panel">
              <Heading size="4">证据链</Heading><Text color="gray" size="2">每一步保存输入、版本和产物</Text>
              {[ [MagnifyingGlass, "多模态检索", "文字、读音、语义、图像和类别"], [Gauge, "确定性评分", "模型不能修改分数和等级"], [Scales, "法律 RAG", "仅引用适用日期内的官方资料"], [FileText, "可编辑报告", "事实与引用校验后再导出"] ].map(([Icon, title, body]) => {
                const TypedIcon = Icon as typeof MagnifyingGlass;
                return <div className="workflow-row" key={String(title)}><TypedIcon size={19} weight="duotone" /><span><strong>{String(title)}</strong><small>{String(body)}</small></span></div>;
              })}
            </aside>
          </section>
        </>
      )}
    </>
  );
}

const analysisSchema = z.object({
  trademarkName: z.string().min(1, "请输入商标名称").max(255),
  description: z.string().min(2, "请简要描述商品或服务").max(4000),
  classes: z.string().min(1, "至少填写一个类别").refine(value => value.split(/[，,\s]+/).every(item => { const number = Number(item); return Number.isInteger(number) && number >= 1 && number <= 45; }), "类别应为 1 到 45 的整数"),
  confirmedOcr: z.string().max(1000).optional()
});
type AnalysisForm = z.infer<typeof analysisSchema>;

function NewAnalysisPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [asset, setAsset] = useState<Awaited<ReturnType<typeof api.uploadAsset>> | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const form = useForm<AnalysisForm>({ resolver: zodResolver(analysisSchema), defaultValues: { trademarkName: "MarkLens", description: "商标检索与风险分析软件服务", classes: "9, 42", confirmedOcr: "" } });
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const submit = form.handleSubmit(async values => {
    try {
      setNotice("正在确认图样和事实…");
      let currentAsset = asset;
      if (file && !currentAsset) {
        currentAsset = await api.uploadAsset(file); setAsset(currentAsset);
        if (currentAsset.ocr_text) form.setValue("confirmedOcr", currentAsset.ocr_text);
        if (currentAsset.ocr_requires_confirmation) { setNotice("OCR 置信度较低，请确认识别文字后再次提交。"); return; }
      }
      const niceClasses = values.classes.split(/[，,\s]+/).filter(Boolean).map(Number);
      const item = await api.createCase({ trademark_name: values.trademarkName, business_description: values.description, nice_classes: niceClasses, image_asset_id: currentAsset?.asset_id ?? null, confirmed_ocr_text: values.confirmedOcr?.trim() || currentAsset?.ocr_text || null });
      const run = await api.createSearch(item.case_id); navigate(`/tasks/${run.run_id}`);
    } catch (error) { setNotice(error instanceof Error ? error.message : "创建失败，请重试。"); }
  });
  function chooseFile(next: File | null) {
    if (preview) URL.revokeObjectURL(preview);
    setFile(next); setAsset(null); setPreview(next ? URL.createObjectURL(next) : null); setNotice(null);
  }
  return (
    <>
      <PageHeader title="新建商标分析" description="提交前先确认事实。DeepSeek 只会接收确认文字和结构化证据，不接收原图。" back="/" />
      <form className="analysis-layout" onSubmit={submit}>
        <section className="form-surface">
          <div className="form-section"><Heading size="4">基本事实</Heading><Text color="gray" size="2">这些字段会进入不可变事实快照</Text></div>
          <label className="field"><span>商标名称</span><TextField.Root size="3" {...form.register("trademarkName")} /><FieldError text={form.formState.errors.trademarkName?.message} /></label>
          <label className="field"><span>业务描述</span><TextArea size="3" rows={5} resize="vertical" {...form.register("description")} /><FieldError text={form.formState.errors.description?.message} /></label>
          <label className="field"><span>国际分类</span><TextField.Root size="3" placeholder="例如：9, 35, 42" {...form.register("classes")} /><small>使用逗号分隔，范围为第 1 至 45 类。</small><FieldError text={form.formState.errors.classes?.message} /></label>
          {(asset?.ocr_text || form.watch("confirmedOcr")) && <label className="field ocr-field"><span>确认 OCR 文字</span><TextField.Root size="3" {...form.register("confirmedOcr")} /><small>识别结果会重新进入文字、读音和语义通道。</small></label>}
          {notice && <Callout.Root color={notice.includes("失败") || notice.includes("较低") ? "amber" : "blue"}><Callout.Icon><Info /></Callout.Icon><Callout.Text>{notice}</Callout.Text></Callout.Root>}
          <Flex gap="3"><Button size="3" type="submit" disabled={form.formState.isSubmitting}>{form.formState.isSubmitting ? <CircleNotch className="spin" /> : <MagnifyingGlass />}启动检索</Button><Button type="button" size="3" variant="soft" color="gray" onClick={() => form.reset()}>重置</Button></Flex>
        </section>
        <aside className="upload-surface">
          <div className="form-section"><Heading size="4">商标图样</Heading><Text color="gray" size="2">PNG、JPEG 或 WebP，不超过 5 MB</Text></div>
          <label className={preview ? "drop-zone has-preview" : "drop-zone"}>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={event => chooseFile(event.target.files?.[0] ?? null)} />
            {preview ? <img src={preview} alt="待分析商标图样预览" /> : <><UploadSimple size={32} weight="duotone" /><strong>选择或拖入图样</strong><span>系统会移除 EXIF 并校验文件头</span></>}
          </label>
          {file && <div className="file-row"><span><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} KB</small></span><button type="button" onClick={() => chooseFile(null)} aria-label="移除图样"><X size={17} /></button></div>}
          <div className="privacy-note"><ShieldCheck size={20} weight="duotone" /><p><strong>图像边界</strong><span>原图只用于本地 OCR、pHash 与图像向量，不发送给 DeepSeek。</span></p></div>
        </aside>
      </form>
    </>
  );
}

function FieldError({ text }: { text?: string }) { return text ? <small className="field-error">{text}</small> : null; }

function taskErrorMessage(code: string, message: string) {
  if (code === "MODEL_NOT_CONFIGURED") return message;
  if (code === "AGENT_EXECUTION_FAILED") return "任务执行失败，请稍后重试。若问题持续，请向维护者提供下方任务编号。";
  return "任务未能完成，请稍后重试。";
}

function TaskPage() {
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const run = useQuery({ queryKey: ["run", runId], queryFn: () => api.getRun(runId), refetchInterval: query => ["completed", "failed"].includes(query.state.data?.status ?? "") ? false : 900 });
  useEffect(() => {
    const data = run.data; if (!data || data.status !== "completed" || !data.resource_id) return;
    const routes: Record<string, string> = { search: `/searches/${data.resource_id}`, risk_analysis: `/risks/${data.resource_id}`, document: `/documents/${data.resource_id}`, consultation: `/consultations/${data.resource_id}`, ingestion_run: `/ingestions/${data.resource_id}` };
    const timer = window.setTimeout(() => navigate(routes[data.resource_type ?? ""] ?? "/"), 450); return () => window.clearTimeout(timer);
  }, [run.data, navigate]);
  if (run.isLoading) return <LoadingState label="正在读取任务状态" />;
  if (run.error) return <ErrorState error={run.error} />;
  if (!run.data) return <ErrorState error={new Error("任务状态为空")} />;
  const data = run.data;
  return <div className="task-page"><motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="task-card">
    <span className={`task-icon ${data.status}`}><AgentIcon type={data.agent_type} /></span><Heading size="6">{data.stage}</Heading><Text color="gray">任务状态会自动刷新，完成后进入对应产物。</Text>
    <Progress value={data.progress} size="3" color={data.status === "failed" ? "red" : "blue"} /><div className="task-meta"><StatusBadge state={data.status} /><span>{data.progress}%</span></div>
    {data.error && <Callout.Root color="red"><Callout.Icon><Warning /></Callout.Icon><Callout.Text><strong>{data.error.code}</strong><br />{taskErrorMessage(data.error.code, data.error.message)}<br /><small>任务编号：{data.run_id}</small></Callout.Text></Callout.Root>}
    {data.error?.code === "MODEL_NOT_CONFIGURED" && <Text size="2" color="gray">请在根目录 .env 中填写 DEEPSEEK_API_KEY，然后重新创建任务。检索功能不受影响。</Text>}
    <Button variant="soft" color="gray" onClick={() => navigate("/")}>返回工作台</Button>
  </motion.div></div>;
}

function AgentIcon({ type }: { type: string }) {
  if (type === "search") return <MagnifyingGlass size={30} weight="duotone" />;
  if (type === "risk") return <Gauge size={30} weight="duotone" />;
  if (type === "document") return <FileText size={30} weight="duotone" />;
  if (type === "ingestion") return <CloudArrowUp size={30} weight="duotone" />;
  return <BookOpenText size={30} weight="duotone" />;
}

function SearchPage() {
  const { searchId = "" } = useParams(); const navigate = useNavigate(); const reduce = useReducedMotion();
  const query = useQuery({ queryKey: ["search", searchId], queryFn: () => api.getSearch(searchId) });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const risk = useMutation({ mutationFn: () => api.createRisk(searchId), onSuccess: run => navigate(`/tasks/${run.run_id}`) });
  if (query.isLoading) return <LoadingState label="正在读取检索证据" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("检索产物为空")} />;
  const bundle = query.data; const selected = bundle.hits.find(item => item.hit_id === selectedId) ?? bundle.hits[0];
  return <>
    <PageHeader title="近似检索结果" description={`已合并 ${bundle.hits.length} 个候选。分数用于教学风险排序，不是官方审查结论。`} back="/new" action={<Button size="3" disabled={!bundle.hits.length || risk.isPending} onClick={() => risk.mutate()}><Gauge />生成风险分析</Button>} />
    {bundle.evidence_quality === "demo_only" && <Callout.Root color="amber" className="page-callout"><Callout.Icon><Warning /></Callout.Icon><Callout.Text>当前命中全部来自明确标注的演示数据。请勿将结果用于真实申请决策。</Callout.Text></Callout.Root>}
    {!bundle.hits.length ? <EmptyState title="没有可用候选" description="当前数据库为空或没有形成有效召回，请先在数据源页面完成同步。" /> : <div className="results-layout">
      <section className="candidate-list" aria-label="相似商标候选">
        <div className="list-toolbar"><span>Top {bundle.top_k}</span><Badge variant="soft">{bundle.evidence_quality}</Badge></div>
        {bundle.hits.map((hit, index) => <motion.button key={hit.hit_id} initial={reduce ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: index * .035 }} onClick={() => setSelectedId(hit.hit_id)} className={hit.hit_id === selected.hit_id ? "candidate-row selected" : "candidate-row"}>
          <CandidateImage hit={hit} /><span className="candidate-main"><span><strong>{hit.name}</strong>{hit.is_demo && <Badge color="gray" variant="soft">演示</Badge>}{!hit.is_demo && hit.jurisdiction !== "CN" && <Badge color="blue" variant="soft">{hit.jurisdiction} 参考</Badge>}</span><small>{hit.application_number}</small><small>{hit.applicant}</small></span><span className="candidate-score"><strong>{Math.round(hit.scores.overall * 100)}</strong><small>综合分</small></span>
        </motion.button>)}
      </section>
      <EvidenceDetail hit={selected} methodology={bundle.methodology} />
    </div>}
  </>;
}

function CandidateImage({ hit }: { hit: TrademarkEvidence }) {
  return hit.image_asset_id ? <img className="candidate-image" src={assetUrl(hit.image_asset_id)} alt={`${hit.name}演示商标图样`} /> : <span className="candidate-image placeholder">{hit.name.slice(0, 1)}</span>;
}

function EvidenceDetail({ hit, methodology }: { hit: TrademarkEvidence; methodology: Record<string, unknown> }) {
  const radar = [ ["视觉", hit.scores.visual], ["文字", hit.scores.text], ["读音", hit.scores.phonetic], ["语义", hit.scores.semantic], ["类别", hit.scores.category] ].map(([subject, value]) => ({ subject, value: Math.round(Number(value ?? 0) * 100) }));
  return <aside className="evidence-detail">
    <div className="evidence-title"><div><Text color="gray" size="2">证据详情</Text><Heading size="5">{hit.name}</Heading></div><span className="score-seal"><strong>{Math.round(hit.scores.overall * 100)}</strong><small>/ 100</small></span></div>
    <div className="image-comparison"><CandidateImage hit={hit} /><div><span>申请人</span><strong>{hit.applicant}</strong><span>类别</span><strong>第 {hit.nice_classes.join("、")} 类</strong><span>状态</span><strong>{hit.status}</strong></div></div>
    <div className="radar-wrap"><ResponsiveContainer width="100%" height={260}><RadarChart data={radar} outerRadius="68%"><PolarGrid stroke="var(--line)" /><PolarAngleAxis dataKey="subject" tick={{ fill: "var(--text-muted)", fontSize: 12 }} /><Radar dataKey="value" stroke="var(--accent)" fill="var(--accent)" fillOpacity={.18} /><ChartTooltip /></RadarChart></ResponsiveContainer></div>
    <div className="reason-block"><Heading size="3">相似理由</Heading>{hit.reasons.map(item => <p key={item}><Check size={16} />{item}</p>)}</div>
    <dl className="model-meta"><div><dt>来源</dt><dd>{hit.source_name}</dd></div><div><dt>记录标识</dt><dd>{hit.source_record_id}</dd></div><div><dt>评分版本</dt><dd>{hit.model_versions.scoring}</dd></div></dl>
    <Text size="1" color="gray">{String(methodology.notice ?? "分数仅供教学演示。")}</Text>
  </aside>;
}

const riskLabels: Record<RiskLevel, { title: string; className: string }> = { high: { title: "高风险", className: "high" }, medium: { title: "中风险", className: "medium" }, low: { title: "低风险", className: "low" }, insufficient_evidence: { title: "证据不足", className: "unknown" } };

function RiskPage() {
  const { analysisId = "" } = useParams(); const navigate = useNavigate();
  const query = useQuery({ queryKey: ["risk", analysisId], queryFn: () => api.getRisk(analysisId) });
  const document = useMutation({ mutationFn: () => api.createDocument(analysisId), onSuccess: run => navigate(`/tasks/${run.run_id}`) });
  if (query.isLoading) return <LoadingState label="正在读取风险分析" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("风险产物为空")} />;
  const data = query.data; const risk = riskLabels[data.risk_level];
  return <>
    <PageHeader title="注册风险分析" description={`分析日期 ${data.analysis_date}，适用 ${data.applicable_law_version}。`} back={`/searches/${data.search_id}`} action={<Button size="3" onClick={() => document.mutate()} disabled={document.isPending}><FileText />生成报告</Button>} />
    <section className={`risk-hero ${risk.className}`}><div className="risk-score"><span>确定性评分</span><strong>{Math.round(data.risk_score * 100)}</strong><small>满分 100</small></div><div><Badge color={data.risk_level === "high" ? "red" : data.risk_level === "medium" ? "amber" : data.risk_level === "low" ? "green" : "gray"}>{risk.title}</Badge><Heading size="6">{data.risk_factors[0]?.title ?? "需要结合证据复核"}</Heading><Text color="gray">{data.risk_factors[0]?.detail ?? data.uncertainties[0]}</Text></div><div className="risk-method"><span>评分归属</span><strong>确定性引擎</strong><span>证据质量</span><strong>{data.evidence_quality}</strong><span>模型可改分数</span><strong>否</strong></div></section>
    <div className="risk-grid"><section className="risk-body">
      <ReportGroup icon={<Warning />} title="主要风险因素">{data.risk_factors.map((item, index) => <article key={index}><strong>{item.title ?? `风险因素 ${index + 1}`}</strong><p>{item.detail ?? String(Object.values(item)[0])}</p></article>)}</ReportGroup>
      <ReportGroup icon={<ShieldCheck />} title="反向证据">{data.counter_evidence.length ? data.counter_evidence.map(item => <p className="line-item" key={item}>{item}</p>) : <Text color="gray">暂无足以降低风险的反向证据。</Text>}</ReportGroup>
      <ReportGroup icon={<FileMagnifyingGlass />} title="修改建议">{data.suggestions.map(item => <p className="line-item" key={item}>{item}</p>)}</ReportGroup>
      {data.uncertainties.length > 0 && <Callout.Root color="amber"><Callout.Icon><Info /></Callout.Icon><Callout.Text><strong>不确定性</strong>{data.uncertainties.map(item => <span className="callout-line" key={item}>{item}</span>)}</Callout.Text></Callout.Root>}
    </section><CitationPanel citations={data.citations} /></div>
    <div className="legal-footer">{data.disclaimer}</div>
  </>;
}

function ReportGroup({ icon, title, children }: { icon: ReactNode; title: string; children: ReactNode }) { return <section className="report-group"><div className="report-group-title">{icon}<Heading size="4">{title}</Heading></div><div>{children}</div></section>; }

function CitationPanel({ citations }: { citations: Citation[] }) {
  return <aside className="citation-panel"><div><Heading size="4">法律引用</Heading><Text color="gray" size="2">仅显示分析日期内有效资料</Text></div>{citations.length ? citations.map((citation, index) => <a href={citation.source_url} target="_blank" rel="noreferrer" key={citation.citation_id} className="citation-card"><span>[{index + 1}] {citation.authority}</span><strong>{citation.title}</strong><small>{citation.locator}</small><p>{citation.excerpt}</p></a>) : <EmptyState title="没有有效引用" description="当前证据不足，不能给出确定性结论。" />}</aside>;
}

function DocumentPage() {
  const { documentId = "" } = useParams(); const queryClient = useQueryClient(); const navigate = useNavigate();
  const query = useQuery({ queryKey: ["document", documentId], queryFn: () => api.getDocument(documentId) });
  const analysisId = query.data?.analysis_id ?? "";
  const riskQuery = useQuery({ queryKey: ["risk", analysisId], queryFn: () => api.getRisk(analysisId), enabled: Boolean(analysisId) });
  const [sections, setSections] = useState<DocumentSection[]>([]);
  const [isEditing, setIsEditing] = useState(false);
  useEffect(() => { if (query.data) setSections(query.data.sections); }, [query.data]);
  const save = useMutation({ mutationFn: () => api.updateDocument(documentId, sections), onSuccess: data => { queryClient.setQueryData(["document", documentId], data); setIsEditing(false); } });
  const validate = useMutation({ mutationFn: () => api.validateDocument(documentId), onSuccess: data => queryClient.setQueryData(["document", documentId], data) });
  if (query.isLoading) return <LoadingState label="正在读取文书初稿" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("文书产物为空")} />;
  const data = query.data;
  const riskData = riskQuery.data;
  const riskMeta = riskData ? riskLabels[riskData.risk_level] : riskLabels.insufficient_evidence;
  const citationNumbers = new Map(data.citations.map((citation, index) => [citation.citation_id, index + 1]));
  const characterCount = sections.reduce((total, section) => total + section.content.length, 0);
  const evidenceQualityLabel = ({ sufficient: "可供初筛", partial: "部分充分", insufficient: "证据不足" } as Record<string, string>)[riskData?.evidence_quality ?? ""] ?? "待核验";
  const generationModeLabel = ({ deepseek: "受约束模型生成", model: "受约束模型生成", template_fallback: "专业模板生成", template: "专业模板生成" } as Record<string, string>)[data.generation_mode] ?? "受控生成";
  return <div className="document-page"><header className="document-toolbar"><button className="back-button" onClick={() => navigate(`/risks/${data.analysis_id}`)} aria-label="返回风险分析"><CaretLeft /></button><div><strong>评估报告</strong><span>已生成约 {characterCount.toLocaleString("zh-CN")} 字，可逐段编辑并重新校验</span></div><Flex gap="2"><Button variant="soft" onClick={() => setIsEditing(value => !value)}>{isEditing ? <Eye /> : <PencilSimple />}{isEditing ? "预览" : "编辑报告"}</Button><Button variant="soft" onClick={() => validate.mutate()} disabled={validate.isPending}><ShieldCheck />校验</Button>{isEditing && <Button onClick={() => save.mutate()} disabled={save.isPending}><Check />保存修改</Button>}<Button color="gray" variant="outline" disabled={!data.can_export || isEditing} onClick={() => window.print()}><Printer />打印 PDF</Button></Flex></header>
    {data.validation_errors.length ? <Callout.Root color="red" className="page-callout"><Callout.Icon><Warning /></Callout.Icon><Callout.Text>发现 {data.validation_errors.length} 个事实或引用问题，修复前禁止正式导出。</Callout.Text></Callout.Root> : <Callout.Root color="green" className="page-callout"><Callout.Icon><ShieldCheck /></Callout.Icon><Callout.Text>当前事实和引用校验通过。导出前仍需人工复核。</Callout.Text></Callout.Root>}
    <div className="editor-layout"><article className="document-sheet"><header className="report-cover"><div className="report-brand"><span>MARKLENS</span><strong>商标注册风险评估</strong></div><div className="report-cover-copy"><span>内部决策参考 / 教学演示</span><h1>{data.title}</h1><p>TRADEMARK REGISTRATION RISK ASSESSMENT</p></div><dl className="report-cover-meta"><div><dt>文书编号</dt><dd>ML-{data.document_id.slice(0, 8).toUpperCase()}</dd></div><div><dt>分析日期</dt><dd>{riskData?.analysis_date ?? "待确认"}</dd></div><div><dt>适用规范</dt><dd>{riskData?.applicable_law_version ?? "正在读取"}</dd></div><div><dt>更新日期</dt><dd>{new Date(data.updated_at).toLocaleDateString("zh-CN")}</dd></div></dl></header><section className={`report-opinion ${riskMeta.className}`}><div><span>初步风险结论</span><strong>{riskMeta.title}</strong><small>结论受证据范围和人工复核约束</small></div><div className="report-score"><span>确定性评分</span><strong>{riskData ? Math.round(riskData.risk_score * 100) : "--"}</strong><small>/ 100</small></div><dl><div><dt>证据质量</dt><dd>{evidenceQualityLabel}</dd></div><div><dt>生成方式</dt><dd>{generationModeLabel}</dd></div><div><dt>法律引用</dt><dd>{data.citations.length} 项</dd></div></dl></section><div className="report-toc"><strong>报告目录</strong><ol>{sections.map((section, index) => <li key={section.section_id}><span>{String(index + 1).padStart(2, "0")}</span>{section.title}</li>)}</ol></div>{sections.map((section, index) => <section key={section.section_id} className="editable-section"><div className="report-section-heading"><span>{String(index + 1).padStart(2, "0")}</span>{isEditing ? <TextField.Root value={section.title} onChange={event => setSections(items => items.map(item => item.section_id === section.section_id ? { ...item, title: event.target.value } : item))} /> : <h2>{section.title}</h2>}</div>{isEditing ? <TextArea rows={Math.min(28, Math.max(8, Math.ceil(section.content.length / 42)))} resize="vertical" value={section.content} onChange={event => setSections(items => items.map(item => item.section_id === section.section_id ? { ...item, content: event.target.value } : item))} /> : <div className="report-copy">{section.content}</div>}{section.citation_ids.length > 0 && <div className="report-section-citations">本节依据 {section.citation_ids.map(id => citationNumbers.get(id)).filter(Boolean).map(number => <span key={number}>[{number}]</span>)}</div>}</section>)}<footer className="report-document-footer"><span>MarkLens 可信商标工作台</span><span>本报告不构成法律意见</span><span>ML-{data.document_id.slice(0, 8).toUpperCase()}</span></footer></article><aside className="report-sidebar"><section className="report-quality"><div><ShieldCheck size={22} /><strong>报告质量控制</strong></div><dl><div><dt>事实一致性</dt><dd>{data.validation_errors.length ? "需要修订" : "校验通过"}</dd></div><div><dt>引用有效性</dt><dd>{data.citations.length ? `${data.citations.length} 项可回溯` : "证据不足"}</dd></div><div><dt>导出状态</dt><dd>{data.can_export ? "允许打印" : "暂缓导出"}</dd></div></dl>{data.validation_errors.length > 0 && <div className="quality-errors">{data.validation_errors.slice(0, 4).map((error, index) => <span key={index}>{String(error.code ?? "VALIDATION_ERROR")}</span>)}</div>}</section><CitationPanel citations={data.citations} /></aside></div>
  </div>;
}

function ConsultationPage() {
  const navigate = useNavigate(); const [question, setQuestion] = useState("文字和图形都有一定差异时，组合商标仍可能被认定近似吗？");
  const mutation = useMutation({ mutationFn: () => api.createConsultation(question), onSuccess: run => navigate(`/tasks/${run.run_id}`) });
  return <><PageHeader title="商标法律咨询" description="回答来自适用日期过滤后的法律资料，并逐条返回可回溯引用。" />
    <div className="consult-layout"><section className="consult-main"><div className="consult-intro"><Scales size={34} weight="duotone" /><div><Heading size="5">先检索证据，再组织回答</Heading><Text color="gray">知识库文本只作为证据数据，不能覆盖系统规则或触发工具。</Text></div></div><label className="field"><span>你的问题</span><TextArea size="3" rows={7} value={question} onChange={event => setQuestion(event.target.value)} /></label><Flex justify="between" align="center"><Text size="1" color="gray">请勿输入个人敏感信息或未公开商业秘密。</Text><Button size="3" disabled={question.trim().length < 3 || mutation.isPending} onClick={() => mutation.mutate()}><BookOpenText />检索并回答</Button></Flex>{mutation.error && <ErrorState error={mutation.error} />}</section><aside className="question-guide"><Heading size="4">适合咨询</Heading>{["商标近似判断通常考虑哪些因素", "商品或服务类别如何影响冲突判断", "驳回风险报告中的引用如何理解", "现行法与未来版本如何按日期适用"].map(item => <button key={item} onClick={() => setQuestion(item)}>{item}<ArrowRight size={15} /></button>)}<Separator size="4" /><Text size="2" color="gray">不提供正式代理、申请提交、诉讼策略或替代律师的确定性结论。</Text></aside></div>
  </>;
}

function ConsultationResultPage() {
  const { consultationId = "" } = useParams(); const query = useQuery({ queryKey: ["consultation", consultationId], queryFn: () => api.getConsultation(consultationId) });
  if (query.isLoading) return <LoadingState label="正在读取咨询答复" />; if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("咨询答复为空")} />;
  const data = query.data; return <><PageHeader title="法律咨询答复" description="答复中的结论强度受证据质量约束。" back="/consult" /><div className="consult-result"><article><div className="question-quote"><span>问题</span><strong>{data.question}</strong></div><div className="answer-copy">{data.answer}</div>{data.uncertainties.length > 0 && <Callout.Root color="amber"><Callout.Icon><Info /></Callout.Icon><Callout.Text>{data.uncertainties.map(item => <span className="callout-line" key={item}>{item}</span>)}</Callout.Text></Callout.Root>}<div className="legal-footer">{data.disclaimer}</div></article><CitationPanel citations={data.citations} /></div></>;
}

function SourcesPage() {
  const queryClient = useQueryClient(); const navigate = useNavigate();
  const query = useQuery({ queryKey: ["sources"], queryFn: api.getSources });
  const sync = useMutation({ mutationFn: (source: SourceDefinition) => api.syncSource(source.source_key), onSuccess: run => { queryClient.invalidateQueries({ queryKey: ["sources"] }); navigate(`/tasks/${run.run_id}`); } });
  return <><PageHeader title="数据源管理" description="只能同步服务端显式注册的适配器。HTTP 适配器必须声明许可、域名白名单和限速。" />
    {query.isLoading ? <LoadingState label="正在读取数据源" /> : query.error ? <ErrorState error={query.error} /> : query.data?.length ? <section className="source-grid">{query.data.map(source => <Card key={source.source_key} className="source-card"><div className="source-top"><span className="source-icon"><Database size={22} weight="duotone" /></span><div><Heading size="4">{source.name}</Heading><Text size="2" color="gray">{source.source_key}</Text></div><StatusBadge state={source.health === "ready" ? "ready" : "unavailable"} /></div><dl><div><dt>适配器</dt><dd>{source.adapter_type.toUpperCase()}</dd></div><div><dt>记录数</dt><dd>{source.record_count}</dd></div><div><dt>最后同步</dt><dd>{source.last_synced_at ? new Date(source.last_synced_at).toLocaleString("zh-CN") : "尚未同步"}</dd></div></dl><div className="license-box"><span>来源许可</span><strong>{source.license_name}</strong><p>{source.terms_summary}</p></div><Button variant="soft" disabled={!source.enabled || source.health !== "ready" || sync.isPending} onClick={() => sync.mutate(source)}><CloudArrowUp />同步数据</Button></Card>)}</section> : <EmptyState title="没有已注册数据源" description="运行 make seed 初始化 JSON 和 CSV 演示适配器。" />}
  </>;
}

function IngestionPage() {
  const { ingestionId = "" } = useParams();
  const query = useQuery({ queryKey: ["ingestion", ingestionId], queryFn: () => api.getIngestion(ingestionId) });
  if (query.isLoading) return <LoadingState label="正在读取导入统计" />;
  if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("导入记录为空")} />;
  const data = query.data;
  return <><PageHeader title="数据同步结果" description={`数据源 ${data.source_key} 的规范化、去重和写入统计。`} back="/sources" />
    <section className="ingestion-summary">{[
      ["读取", data.fetched_count], ["新增", data.created_count], ["更新", data.updated_count],
      ["未变化", data.skipped_count], ["失败", data.failed_count]
    ].map(([label, value]) => <div key={String(label)}><span>{label}</span><strong>{value}</strong></div>)}</section>
    {data.errors.length ? <section className="error-records"><Heading size="4">失败记录</Heading>{data.errors.map((error, index) => <div key={index}><Badge color="red">{String(error.record ?? error.cursor ?? index + 1)}</Badge><span>{String(error.error ?? "未知错误")}</span></div>)}</section> : <EmptyState title="同步记录通过" description="本次分页中的记录均完成校验或幂等跳过。" />}
  </>;
}

function CasePage() {
  const { caseId = "" } = useParams(); const navigate = useNavigate();
  const query = useQuery({ queryKey: ["case", caseId], queryFn: async () => { const response = await fetch(`/api/v1/cases/${caseId}`); if (!response.ok) throw new Error("案件不存在"); return response.json(); } });
  const search = useMutation({ mutationFn: () => api.createSearch(caseId), onSuccess: run => navigate(`/tasks/${run.run_id}`) });
  if (query.isLoading) return <LoadingState />; if (query.error) return <ErrorState error={query.error} />;
  if (!query.data) return <ErrorState error={new Error("案件事实为空")} />;
  const item = query.data; return <><PageHeader title={item.trademark_name} description="已确认的案件事实快照" back="/" action={<Button onClick={() => search.mutate()}><MagnifyingGlass />重新检索</Button>} /><Card className="case-detail"><dl><div><dt>业务描述</dt><dd>{item.business_description}</dd></div><div><dt>国际分类</dt><dd>第 {item.nice_classes.join("、")} 类</dd></div><div><dt>OCR 文字</dt><dd>{item.confirmed_ocr_text || "未提供"}</dd></div><div><dt>创建时间</dt><dd>{new Date(item.created_at).toLocaleString("zh-CN")}</dd></div></dl>{item.image_asset_id && <img src={assetUrl(item.image_asset_id)} alt={`${item.trademark_name}商标图样`} />}</Card></>;
}

function NotFoundPage() { const navigate = useNavigate(); return <EmptyState title="页面不存在" description="链接可能已失效，返回工作台继续操作。" action={<Button onClick={() => navigate("/")}>返回工作台</Button>} />; }

export function App() {
  const [appearance, setAppearanceState] = useState<Appearance>(initialAppearance);
  function setAppearance(value: Appearance) { setAppearanceState(value); localStorage.setItem("marklens-theme", value); }
  return <Theme appearance={appearance} accentColor="blue" grayColor="slate" radius="medium" scaling="100%"><AppShell appearance={appearance} setAppearance={setAppearance}><Routes>
    <Route path="/" element={<HomePage />} /><Route path="/new" element={<NewAnalysisPage />} /><Route path="/tasks/:runId" element={<TaskPage />} />
    <Route path="/cases/:caseId" element={<CasePage />} /><Route path="/searches/:searchId" element={<SearchPage />} /><Route path="/risks/:analysisId" element={<RiskPage />} />
    <Route path="/documents/:documentId" element={<DocumentPage />} /><Route path="/consult" element={<ConsultationPage />} /><Route path="/consultations/:consultationId" element={<ConsultationResultPage />} />
    <Route path="/sources" element={<SourcesPage />} /><Route path="/ingestions/:ingestionId" element={<IngestionPage />} /><Route path="*" element={<NotFoundPage />} />
  </Routes></AppShell></Theme>;
}
