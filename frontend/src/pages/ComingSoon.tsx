export default function ComingSoon({ title, note }: { title: string; note: string }) {
  return (
    <div className="max-w-xl">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="mt-2 text-muted">{note}</p>
    </div>
  );
}
