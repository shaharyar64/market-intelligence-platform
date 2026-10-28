"use client";

import { Children, isValidElement, type ReactNode } from "react";
import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { toStructuredMarkdown } from "@/lib/assistantResponse";

function plainText(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) => {
      if (typeof child === "string" || typeof child === "number") return String(child);
      if (isValidElement<{ children?: ReactNode }>(child)) return plainText(child.props.children);
      return "";
    })
    .join("");
}

function Heading({ children }: { children?: ReactNode }) {
  return (
    <h3 className="flex items-center gap-2 pt-2 text-[13px] font-semibold tracking-tight" style={{ color: "var(--title-tx)" }}>
      <span className="h-3.5 w-1 rounded-full bg-gradient-to-b from-indigo-500 to-sky-400" />
      {children}
    </h3>
  );
}

const components: Components = {
  h1: Heading,
  h2: Heading,
  h3: Heading,
  h4: Heading,
  p: ({ children }) =>
    /^\s*(source|note)s?\s*:/i.test(plainText(children)) ? (
      <p className="border-t pt-3 text-xs leading-5" style={{ borderColor: "var(--card-bd)", color: "var(--muted-tx)" }}>
        {children}
      </p>
    ) : (
      <p className="leading-[1.7]" style={{ color: "var(--body-tx)" }}>{children}</p>
    ),
  ol: ({ children }) => (
    <ol className="list-decimal space-y-2 pl-5 marker:text-xs marker:font-semibold marker:text-indigo-500" style={{ color: "var(--body-tx)" }}>
      {children}
    </ol>
  ),
  ul: ({ children }) => (
    <ul className="list-disc space-y-2 pl-5 marker:text-indigo-400" style={{ color: "var(--body-tx)" }}>
      {children}
    </ul>
  ),
  li: ({ children }) => <li className="pl-1 leading-[1.65]">{children}</li>,
  strong: ({ children }) => <strong className="font-semibold" style={{ color: "var(--title-tx)" }}>{children}</strong>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: "var(--accent-tx)" }}>
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="overflow-x-auto rounded-xl border" style={{ borderColor: "var(--card-bd)", background: "var(--card-bg-2)" }}>
      <table className="w-full border-collapse text-left text-[13px] tabular-nums">{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead className="bg-indigo-500/[0.06]">{children}</thead>,
  tr: ({ children }) => <tr className="transition-colors hover:bg-indigo-500/[0.04]">{children}</tr>,
  th: ({ children, style }) => (
    <th
      className="whitespace-nowrap px-3.5 py-2.5 text-[11px] font-semibold uppercase tracking-wide"
      style={{ ...style, color: "var(--muted-tx)" }}
    >
      {children}
    </th>
  ),
  td: ({ children, style }) => (
    <td
      className="border-t px-3.5 py-2.5 align-top first:font-medium"
      style={{ ...style, borderColor: "var(--card-bd)", color: "var(--body-tx)" }}
    >
      {children}
    </td>
  ),
};

export default function StructuredResponse({ text }: { text: string }) {
  return (
    <div className="space-y-3.5 text-sm [&_li>ol]:mt-2 [&_li>ul]:mt-2 [&_td:first-child]:text-[color:var(--title-tx)]">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {toStructuredMarkdown(text)}
      </ReactMarkdown>
    </div>
  );
}
