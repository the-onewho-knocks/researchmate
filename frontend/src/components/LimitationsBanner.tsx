export default function LimitationsBanner({ items }: { items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="banner">
      <strong>Good to know</strong>
      <ul>
        {items.map((l, i) => (
          <li key={i}>{l}</li>
        ))}
      </ul>
    </div>
  );
}
