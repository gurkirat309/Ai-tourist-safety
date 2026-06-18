import { useEffect, useRef, useState } from "react";
import { MapPin, Search, LocateFixed, ChevronDown, X } from "lucide-react";
import { api } from "../lib/api";

// A combobox for choosing a place: curated Bengaluru suggestions + free-text
// geocoding + (optionally) "use my current location". Calls onChange with
// { name, lat, lon }.
export default function PlacePicker({
  label,
  value,
  onChange,
  curated = [],
  allowMyLocation = false,
  placeholder = "Search a place…",
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const boxRef = useRef(null);

  // Close on outside click.
  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  // Debounced geocode search for free text.
  useEffect(() => {
    if (query.trim().length < 3) {
      setResults([]);
      return;
    }
    setSearching(true);
    const t = setTimeout(() => {
      api
        .placeSearch(query.trim())
        .then((d) => setResults(d.results || []))
        .catch(() => setResults([]))
        .finally(() => setSearching(false));
    }, 450);
    return () => clearTimeout(t);
  }, [query]);

  const q = query.trim().toLowerCase();
  const filteredCurated = q
    ? curated.filter((p) => p.name.toLowerCase().includes(q))
    : curated;

  function pick(p) {
    onChange({ name: p.name, lat: p.lat, lon: p.lon });
    setOpen(false);
    setQuery("");
    setResults([]);
  }

  function useMyLocation() {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition((pos) => {
      pick({ name: "My current location", lat: +pos.coords.latitude.toFixed(5), lon: +pos.coords.longitude.toFixed(5) });
    });
  }

  return (
    <div className="relative" ref={boxRef}>
      {label && <span className="mb-1 block text-sm font-medium text-slate-600">{label}</span>}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg border border-slate-300 px-3 py-2 text-left text-sm outline-none focus:border-brand-500"
      >
        <span className={value ? "flex items-center gap-2 text-slate-800" : "text-slate-400"}>
          {value && <MapPin size={14} className="text-brand-600" />}
          {value ? value.name : placeholder}
        </span>
        <ChevronDown size={16} className="text-slate-400" />
      </button>

      {open && (
        <div className="absolute z-[1200] mt-1 w-full overflow-hidden rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center gap-2 border-b border-slate-100 px-3 py-2">
            <Search size={14} className="text-slate-400" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Type to search…"
              className="w-full text-sm outline-none"
            />
            {query && (
              <button onClick={() => setQuery("")} className="text-slate-400 hover:text-slate-600">
                <X size={14} />
              </button>
            )}
          </div>

          <div className="max-h-64 overflow-auto py-1">
            {allowMyLocation && !q && (
              <button
                onClick={useMyLocation}
                className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm text-brand-700 hover:bg-brand-50"
              >
                <LocateFixed size={14} /> Use my current location
              </button>
            )}

            {filteredCurated.length > 0 && (
              <div className="px-3 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Popular places
              </div>
            )}
            {filteredCurated.map((p) => (
              <button
                key={p.name}
                onClick={() => pick(p)}
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <span className="text-slate-700">{p.name}</span>
                <span className="text-xs text-slate-400">{p.category}</span>
              </button>
            ))}

            {results.length > 0 && (
              <div className="px-3 pt-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Search results
              </div>
            )}
            {results.map((r, i) => (
              <button
                key={`${r.name}-${i}`}
                onClick={() => pick(r)}
                className="block w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
              >
                <div className="text-slate-700">{r.name}</div>
                {r.full_name && (
                  <div className="truncate text-xs text-slate-400">{r.full_name}</div>
                )}
              </button>
            ))}

            {q && !searching && filteredCurated.length === 0 && results.length === 0 && (
              <div className="px-3 py-3 text-sm text-slate-400">No matches.</div>
            )}
            {searching && <div className="px-3 py-3 text-sm text-slate-400">Searching…</div>}
          </div>
        </div>
      )}
    </div>
  );
}
