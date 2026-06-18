import { useState } from "react";
import { Bot, X, Send } from "lucide-react";

// Floating AI-assistant placeholder. The real conversational agent is a planned
// feature; this establishes the entry point and UX shell.
export default function AssistantWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-[1100] flex h-96 w-80 flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl">
          <div className="flex items-center justify-between bg-brand-600 px-4 py-3 text-white">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Bot size={18} /> Safety Assistant
            </div>
            <button onClick={() => setOpen(false)} className="rounded p-1 hover:bg-white/20">
              <X size={16} />
            </button>
          </div>
          <div className="flex-1 space-y-3 overflow-auto bg-slate-50 p-4">
            <div className="max-w-[85%] rounded-lg rounded-tl-none bg-white px-3 py-2 text-sm text-slate-700 shadow-sm">
              Hi! I'm your safety assistant. I'll soon be able to answer questions
              like "is my route safe?" or "what should I do right now?".
            </div>
            <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700 ring-1 ring-inset ring-amber-200">
              🚧 Conversational AI is a planned feature — coming soon.
            </div>
          </div>
          <div className="flex items-center gap-2 border-t border-slate-100 p-3">
            <input
              disabled
              placeholder="Ask the assistant… (coming soon)"
              className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-400"
            />
            <button disabled className="rounded-lg bg-slate-200 p-2 text-slate-400">
              <Send size={16} />
            </button>
          </div>
        </div>
      )}
      <button
        onClick={() => setOpen((v) => !v)}
        title="Safety assistant"
        className="fixed bottom-6 right-6 z-[1100] grid h-14 w-14 place-items-center rounded-full bg-brand-600 text-white shadow-lg transition hover:bg-brand-700"
      >
        <Bot size={24} />
      </button>
    </>
  );
}
