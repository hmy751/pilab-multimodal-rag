import Link from "next/link";

export default function NotFound() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="glass-panel max-w-xl p-8 text-center">
        <p className="text-[11px] uppercase tracking-[0.28em] text-white/42">
          404
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-[-0.04em] text-white">
          요청한 실험 페이지를 찾을 수 없습니다.
        </h1>
        <p className="mt-4 text-sm leading-7 text-white/64">
          정적 프로토타입에는 4개의 실험 페이지만 포함되어 있습니다. 갤러리로
          돌아가서 다른 실험을 둘러보세요.
        </p>
        <Link
          href="/"
          className="mt-6 inline-flex rounded-full border border-white/10 bg-white/[0.04] px-5 py-3 text-sm text-white/78 transition hover:text-white"
        >
          갤러리로 이동
        </Link>
      </div>
    </main>
  );
}
