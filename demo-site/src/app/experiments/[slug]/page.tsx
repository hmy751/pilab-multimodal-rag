import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { ExperimentDetail } from "@/components/portfolio";
import { experiments, getExperiment } from "@/lib/experiments";

export function generateStaticParams() {
  return experiments.map((experiment) => ({ slug: experiment.slug }));
}

export function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Metadata {
  const experiment = getExperiment(params.slug);

  if (!experiment) {
    return {
      title: "실험을 찾을 수 없습니다",
    };
  }

  return {
    title: `${experiment.title} | AI 엔지니어링 실험실`,
    description: experiment.oneLiner,
  };
}

export default function ExperimentPage({
  params,
}: {
  params: { slug: string };
}) {
  const experiment = getExperiment(params.slug);

  if (!experiment) {
    notFound();
  }

  return <ExperimentDetail experiment={experiment} />;
}
