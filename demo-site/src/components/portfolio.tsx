import Link from "next/link";
import {
  ArrowLeft,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Play,
  Sparkles,
} from "lucide-react";

import { experiments, type Experiment } from "@/lib/experiments";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

function statusTone(status: Experiment["timeline"][number]["status"]) {
  if (status === "success") {
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }

  if (status === "fail") {
    return "border-rose-400/30 bg-rose-400/10 text-rose-200";
  }

  return "border-amber-300/30 bg-amber-300/10 text-amber-100";
}

function valueTone(value: string) {
  if (
    value.includes("성공") ||
    value.includes("✅") ||
    value === "✓" ||
    value.includes("복원")
  ) {
    return "text-emerald-300";
  }

  if (value.includes("실패") || value === "✗" || value.includes("후퇴")) {
    return "text-rose-300";
  }

  if (value.includes("부분") || value.includes("개선")) {
    return "text-amber-200";
  }

  return "text-white/80";
}

function HeaderBar() {
  return (
    <header className="mx-auto flex w-full max-w-[1520px] px-4 pt-4 md:px-6">
      <div className="glass-panel flex w-full flex-col gap-4 px-5 py-4 md:flex-row md:items-center md:justify-between md:px-6">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.06]">
            <Sparkles className="h-5 w-5 text-white/85" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.32em] text-white/42">
              Multimodal Experiment Log
            </p>
            <p className="mt-1 text-base font-medium text-white/88">
              실험, 지표, 해결 과정
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="pill">{experiments.length} Experiments</span>
          <span className="pill">Retrieval · Vision · Metadata</span>
          <span className="pill">Updated Apr 2026</span>
        </div>
      </div>
    </header>
  );
}

function Artwork({ experiment, detail = false }: { experiment: Experiment; detail?: boolean }) {
  const baseStyle = {
    background: `linear-gradient(135deg, ${experiment.art.base} 0%, ${experiment.art.accent} 100%)`,
  };

  return (
    <div
      className={cx(
        "relative overflow-hidden rounded-[28px] border border-white/10",
        detail ? "aspect-[4/3]" : "aspect-[16/11]",
      )}
      style={baseStyle}
    >
      <div
        className="animate-drift absolute inset-[-18%] opacity-90 blur-3xl"
        style={{
          background: `radial-gradient(circle, ${experiment.art.glow} 0%, transparent 55%)`,
        }}
      />
      <div className="absolute inset-0 bg-[linear-gradient(135deg,rgba(255,255,255,0.12),transparent_35%,rgba(0,0,0,0.28)_100%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(transparent_0%,rgba(6,6,8,0.1)_50%,rgba(6,6,8,0.5)_100%)]" />

      {experiment.art.variant === "cat" && (
        <>
          {detail ? (
            <>
              <div className="absolute left-8 top-7 h-16 w-16 rounded-full border border-white/30 bg-white/10" />
              <div className="absolute left-16 top-16 h-48 w-48 rounded-full bg-[#fef08a]/20 blur-3xl" />
              <div className="absolute right-10 top-12 h-52 w-40 rounded-[32px] border border-white/20 bg-black/25 backdrop-blur-sm" />
            </>
          ) : null}
          <div className="absolute bottom-0 left-0 right-0 h-[34%] bg-[linear-gradient(180deg,transparent,rgba(0,0,0,0.4))]" />
        </>
      )}

      {experiment.art.variant === "code" && (
        <>
          {detail ? (
            <>
              <div className="absolute inset-x-8 top-8 h-12 rounded-2xl border border-cyan-200/25 bg-black/30" />
              <div className="absolute inset-x-10 top-11 h-px bg-cyan-100/20" />
              <div className="absolute left-10 top-24 h-[1px] w-[60%] bg-cyan-100/35" />
              <div className="absolute left-10 top-32 h-[1px] w-[42%] bg-cyan-100/20" />
              <div className="absolute left-10 top-40 h-[1px] w-[52%] bg-cyan-100/25" />
              <div className="absolute right-8 top-20 h-40 w-24 rounded-[28px] border border-cyan-100/25 bg-white/10" />
            </>
          ) : null}
          <div className="absolute bottom-0 left-0 right-0 h-24 bg-[linear-gradient(180deg,transparent,rgba(1,4,10,0.5))]" />
        </>
      )}

      {experiment.art.variant === "cctv" && (
        <>
          <div className="absolute inset-0 bg-[repeating-linear-gradient(180deg,rgba(255,255,255,0.05)_0px,rgba(255,255,255,0.05)_1px,transparent_2px,transparent_8px)] opacity-35" />
          <div className="absolute left-1/2 top-1/2 h-32 w-32 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/25" />
          <div className="absolute left-1/2 top-1/2 h-px w-48 -translate-x-1/2 -translate-y-1/2 bg-white/20" />
          <div className="absolute left-1/2 top-1/2 h-48 w-px -translate-x-1/2 -translate-y-1/2 bg-white/20" />
          <div className="animate-scan absolute inset-x-4 h-20 bg-[linear-gradient(180deg,transparent,rgba(255,255,255,0.15),transparent)] opacity-50" />
        </>
      )}

      {experiment.art.variant === "movie" && (
        <>
          <div className="absolute left-8 top-8 flex gap-2">
            {[0.35, 0.55, 0.8].map((opacity, index) => (
              <div
                key={index}
                className="w-20 rounded-full border border-white/10 bg-white"
                style={{ height: `${72 + index * 18}px`, opacity }}
              />
            ))}
          </div>
          <div className="absolute bottom-10 right-10 h-52 w-52 rounded-full border border-rose-100/20 bg-black/20 backdrop-blur-sm" />
          <div className="absolute inset-x-8 bottom-8 h-px bg-white/20" />
          <div className="absolute inset-x-8 bottom-14 h-px bg-white/8" />
        </>
      )}

      <div className="absolute left-5 top-5 z-20 flex items-center gap-2">
        <span className="pill border-white/20 bg-black/45 text-white/90 backdrop-blur-md">
          {experiment.art.tag}
        </span>
      </div>

      <div className="absolute bottom-5 left-5 right-5">
        <p className="text-[11px] uppercase tracking-[0.32em] text-white/60">
          {experiment.art.eyebrow}
        </p>
        <h3
          className={cx(
            "mt-3 font-semibold tracking-[-0.04em] text-white",
            detail ? "text-5xl md:text-6xl" : "text-4xl",
          )}
        >
          {experiment.art.headline}
        </h3>
        <p className="mt-3 max-w-md text-sm leading-6 text-white/78">
          {experiment.kicker}
        </p>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section className="glass-panel relative overflow-hidden px-6 py-6 md:px-8 md:py-7">
      <div className="absolute right-0 top-0 h-44 w-44 rounded-full bg-emerald-500/10 blur-3xl" />
      <div className="absolute bottom-0 left-12 h-32 w-32 rounded-full bg-amber-400/10 blur-3xl" />

      <div className="max-w-5xl">
        <span className="pill">AI Engineering Lab</span>
        <h1 className="mt-4 max-w-4xl text-3xl font-semibold tracking-[-0.05em] text-white md:text-5xl">
          멀티모달 RAG 기반
          <br />
          질의응답 시스템 고도화
        </h1>
        <p className="mt-4 max-w-4xl text-sm leading-7 text-white/68 md:text-base">
          1개월 동안 실험한 멀티모달 RAG 파이프라인을 스토리 중심으로
          정리했습니다. <br />각 카드에는 실패 지점, 해결 레이어, 최종 지표를 한
          화면에서 빠르게 읽을 수 있게 압축해두었습니다.
        </p>
      </div>
    </section>
  );
}

function ExperimentCard({ experiment }: { experiment: Experiment }) {
  return (
    <Link
      href={`/experiments/${experiment.slug}`}
      className="group block"
    >
      <article className="glass-panel h-full overflow-hidden p-3 transition duration-300 group-hover:-translate-y-1 group-hover:border-white/20 md:p-4">
        <Artwork experiment={experiment} />

        <div className="px-2 pb-1 pt-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] uppercase tracking-[0.3em] text-white/45">
                case {experiment.shortLabel}
              </p>
              <h2 className="mt-2 text-xl font-semibold tracking-[-0.04em] text-white md:text-[1.65rem]">
                {experiment.title}
              </h2>
            </div>
            <span className="rounded-full border border-white/10 bg-white/[0.04] p-3 text-white/65 transition group-hover:text-white">
              <ArrowUpRight className="h-4 w-4" />
            </span>
          </div>

          <p className="mt-3 text-sm font-medium text-white/76">{experiment.kicker}</p>
          <p className="mt-3 text-sm leading-6 text-white/60">
            {experiment.oneLiner}
          </p>

          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            {experiment.cardStats.map((stat) => (
              <div
                key={stat.label}
                className="rounded-[18px] border border-white/10 bg-white/[0.03] p-2.5"
              >
                <p className="text-[10px] uppercase tracking-[0.25em] text-white/42">
                  {stat.label}
                </p>
                <p className="mt-2 text-sm font-medium text-white/82">
                  {stat.value}
                </p>
              </div>
            ))}
          </div>
        </div>
      </article>
    </Link>
  );
}

function SectionCard({
  index,
  title,
  children,
}: {
  index: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="glass-panel bg-panel p-5 md:p-6">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-full border border-white/10 bg-white/[0.04] text-sm font-semibold text-white/85">
          {index}
        </span>
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-white/42">
            Section
          </p>
          <h2 className="text-xl font-semibold tracking-[-0.03em] text-white">
            {title}
          </h2>
        </div>
      </div>
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ComparisonTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: string[][];
}) {
  return (
    <div className="overflow-x-auto rounded-[24px] border border-white/10">
      <table className="min-w-full border-collapse text-left">
        <thead className="bg-white/[0.04]">
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                className="px-4 py-3 text-xs uppercase tracking-[0.24em] text-white/45"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={`${row[0]}-${rowIndex}`}
              className="border-t border-white/10 bg-black/10"
            >
              {row.map((cell, cellIndex) => (
                <td
                  key={`${cell}-${cellIndex}`}
                  className={cx(
                    "px-4 py-3 text-sm whitespace-nowrap",
                    cellIndex === 0 ? "text-white/90" : valueTone(cell),
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DetailSidebar({ experiment }: { experiment: Experiment }) {
  return (
    <aside className="space-y-4 xl:sticky xl:top-6 xl:self-start">
      <div className="glass-panel p-4 md:p-5">
        <Artwork experiment={experiment} detail />

        <div className="mt-5 flex flex-wrap gap-2">
          <span className="pill">{experiment.dataset}</span>
          <span className="pill">{experiment.duration}</span>
          <span className="pill">{experiment.artifact}</span>
        </div>

        <h1 className="mt-5 text-3xl font-semibold tracking-[-0.04em] text-white md:text-4xl">
          {experiment.title}
        </h1>
        <p className="mt-3 text-base leading-8 text-white/68">
          {experiment.oneLiner}
        </p>

        <div className="mt-5 flex items-center gap-3 rounded-[24px] border border-white/10 bg-black/20 p-4">
          <div className="flex h-12 w-12 items-center justify-center rounded-full border border-white/10 bg-white/[0.06]">
            <Play className="h-5 w-5 text-white/80" />
          </div>
          <div>
            <p className="text-[11px] uppercase tracking-[0.24em] text-white/42">
              Prototype media
            </p>
            <p className="mt-1 text-sm text-white/72">
              영상 플레이어 대신 썸네일형 모션 패널로 구조를 먼저 검증했습니다.
            </p>
          </div>
        </div>
      </div>

      <div className="glass-panel p-5">
        <p className="text-[11px] uppercase tracking-[0.28em] text-white/42">
          Pipeline
        </p>
        <div className="mt-4 space-y-3">
          {experiment.architecture.map((step, index) => (
            <div
              key={step}
              className="flex items-center gap-3 rounded-[22px] border border-white/10 bg-black/15 px-4 py-3"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full border border-white/10 bg-white/[0.05] text-xs font-semibold text-white/80">
                {index + 1}
              </span>
              <span className="text-sm text-white/80">{step}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="glass-panel p-5">
        <div className="flex items-center gap-3">
          <Clock3 className="h-4 w-4 text-white/55" />
          <p className="text-[11px] uppercase tracking-[0.28em] text-white/42">
            Prototype note
          </p>
        </div>
        <p className="mt-3 text-sm leading-7 text-white/64">{experiment.teamNote}</p>
      </div>
    </aside>
  );
}

export function PortfolioHome() {
  return (
    <div className="pb-14">
      <HeaderBar />
      <main className="mx-auto mt-4 max-w-[1520px] px-4 md:px-6">
        <Hero />

        <section className="mt-5 grid gap-5 md:grid-cols-2">
          {experiments.map((experiment) => (
            <ExperimentCard key={experiment.slug} experiment={experiment} />
          ))}
        </section>
      </main>
    </div>
  );
}

export function ExperimentDetail({ experiment }: { experiment: Experiment }) {
  const currentIndex = experiments.findIndex((item) => item.slug === experiment.slug);
  const prev = experiments[(currentIndex - 1 + experiments.length) % experiments.length];
  const next = experiments[(currentIndex + 1) % experiments.length];

  return (
    <div className="pb-14">
      <HeaderBar />

      <main className="mx-auto mt-6 max-w-[1520px] px-4 md:px-6">
        <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <Link
            href="/"
            className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/72 transition hover:text-white"
          >
            <ArrowLeft className="h-4 w-4" />
            갤러리로 돌아가기
          </Link>

          <div className="flex flex-wrap items-center gap-3">
            <Link
              href={`/experiments/${prev.slug}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/70 transition hover:text-white"
            >
              <ChevronLeft className="h-4 w-4" />
              이전 실험
            </Link>
            <Link
              href={`/experiments/${next.slug}`}
              className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-4 py-3 text-sm text-white/70 transition hover:text-white"
            >
              다음 실험
              <ChevronRight className="h-4 w-4" />
            </Link>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.1fr)]">
          <DetailSidebar experiment={experiment} />

          <div className="space-y-4">
            <SectionCard index="01" title="문제 의식">
              <div className="space-y-4 text-base leading-8 text-white/72">
                {experiment.problemStatement.map((paragraph) => (
                  <p key={paragraph}>{paragraph}</p>
                ))}
              </div>
            </SectionCard>

            <SectionCard index="02" title="핵심 질문">
              <div className="rounded-[28px] border border-white/10 bg-black/20 p-5 md:p-6">
                <p className="text-2xl font-semibold leading-10 tracking-[-0.04em] text-white md:text-3xl">
                  “{experiment.question}”
                </p>
                <div className="mt-5 rounded-[24px] border border-rose-400/25 bg-rose-400/10 p-4">
                  <p className="text-[11px] uppercase tracking-[0.24em] text-rose-200/70">
                    First answer
                  </p>
                  <p className="mt-2 text-lg text-rose-100">
                    {experiment.firstAttempt.answer}
                  </p>
                  <p className="mt-2 text-sm leading-7 text-rose-100/70">
                    {experiment.firstAttempt.note}
                  </p>
                </div>
              </div>
            </SectionCard>

            <SectionCard index="03" title="첫 시도 → 실패">
              <div className="space-y-3">
                {experiment.failureAnalysis.map((item) => (
                  <div
                    key={item}
                    className="rounded-[24px] border border-white/10 bg-black/15 p-4 text-sm leading-7 text-white/68"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard index="04" title="해결 과정">
              <div className="space-y-3">
                {experiment.timeline.map((step) => (
                  <div
                    key={step.label}
                    className="grid gap-3 rounded-[26px] border border-white/10 bg-black/15 p-4 md:grid-cols-[auto_minmax(0,1fr)]"
                  >
                    <div
                      className={cx(
                        "inline-flex h-fit items-center rounded-full border px-3 py-1 text-xs uppercase tracking-[0.25em]",
                        statusTone(step.status),
                      )}
                    >
                      {step.label}
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white/88">{step.change}</p>
                      <p className="mt-2 text-sm leading-7 text-white/64">
                        {step.outcome}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>

            <SectionCard index="05" title="최종 정답">
              <div className="rounded-[28px] border border-emerald-400/25 bg-emerald-400/10 p-5 md:p-6">
                <p className="text-[11px] uppercase tracking-[0.24em] text-emerald-200/70">
                  Final answer
                </p>
                <p className="mt-3 text-xl font-semibold leading-9 tracking-[-0.03em] text-emerald-100 md:text-2xl">
                  {experiment.finalAnswer.answer}
                </p>
                <p className="mt-4 text-sm leading-7 text-emerald-50/78">
                  {experiment.finalAnswer.summary}
                </p>

                <div className="mt-6 grid gap-3 md:grid-cols-3">
                  {experiment.finalAnswer.improvements.map((improvement) => (
                    <div
                      key={improvement.label}
                      className="rounded-[22px] border border-emerald-200/15 bg-black/15 p-4"
                    >
                      <p className="text-[10px] uppercase tracking-[0.24em] text-emerald-100/60">
                        {improvement.label}
                      </p>
                      <div className="mt-3 flex items-center gap-2 text-sm">
                        <span className="text-white/55">{improvement.before}</span>
                        <ArrowUpRight className="h-4 w-4 text-emerald-200" />
                        <span className="font-semibold text-emerald-100">
                          {improvement.after}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </SectionCard>

            <SectionCard index="06" title="모델 선택 이유">
              <ComparisonTable
                columns={["역할", "선택 모델", "이유"]}
                rows={experiment.modelChoices.map((choice) => [
                  choice.role,
                  choice.model,
                  choice.reason,
                ])}
              />
            </SectionCard>

            <SectionCard index="07" title="사용 기술">
              <div className="flex flex-wrap gap-3">
                {experiment.techBadges.map((badge) => (
                  <span key={badge} className="pill">
                    {badge}
                  </span>
                ))}
              </div>
            </SectionCard>

            <SectionCard index="08" title="평가 결과 비교표">
              <ComparisonTable
                columns={experiment.comparison.columns}
                rows={experiment.comparison.rows}
              />
            </SectionCard>

            <SectionCard index="09" title="배운 점">
              <div className="space-y-3">
                {experiment.learnings.map((item) => (
                  <div
                    key={item}
                    className="rounded-[24px] border border-white/10 bg-black/15 p-4 text-sm leading-7 text-white/68"
                  >
                    {item}
                  </div>
                ))}
              </div>
            </SectionCard>

            <details className="glass-panel overflow-hidden p-5">
              <summary className="cursor-pointer list-none text-sm font-medium text-white/78">
                프로토타입 스냅샷 보기
              </summary>
              <div className="mt-4 rounded-[24px] border border-white/10 bg-black/25 p-4">
                <pre className="overflow-x-auto text-xs leading-6 text-white/65">
                  {JSON.stringify(experiment.snapshot, null, 2)}
                </pre>
              </div>
            </details>
          </div>
        </div>
      </main>
    </div>
  );
}
