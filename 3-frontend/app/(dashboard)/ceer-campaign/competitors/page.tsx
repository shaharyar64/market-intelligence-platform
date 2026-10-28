"use client";

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getCompetitorMentions } from "@/lib/ceerCampaign";
import { useAsyncResource } from "@/lib/useAsyncResource";
import { axis, CampaignShell, Chart, Load, number, Panel, platform, s, tooltip } from "../shared";

export default function CompetitorMentionsPage() {
  const data = useAsyncResource(getCompetitorMentions, []);
  return <CampaignShell title="Competitor mentions" description="Other automotive references people use when discussing CEER.">
    <section className={s.section}><Panel title="Most-mentioned references" description="Each bar is the number of collected comments that mention the reference.">
      <Load resource={data}>{({ references }) => <Chart label="Comments mentioning each automotive reference"><ResponsiveContainer width="100%" height="100%"><BarChart data={references} layout="vertical" margin={{ left: 8, right: 44 }}><CartesianGrid horizontal={false} stroke="var(--ceer-line)" strokeDasharray="3 4"/><XAxis {...axis} type="number" allowDecimals={false}/><YAxis {...axis} type="category" dataKey="reference" width={150}/><Tooltip contentStyle={tooltip} formatter={(value) => [number(Number(value)), "Comments"]}/><Bar dataKey="mentions" fill="var(--ceer-accent)" radius={[0, 4, 4, 0]}><LabelList dataKey="mentions" position="right" fill="var(--ceer-ink)" fontSize={11}/></Bar></BarChart></ResponsiveContainer></Chart>}</Load>
    </Panel></section>
    <section className={s.section}><Panel title="How CEER is being compared" description="Ranked by the number of comments that mention each reference. The context column explains the usual comparison, not a verdict about CEER.">
      <Load resource={data}>{({ references }) => <div className={s.tableWrap}><table className={s.table}><thead><tr><th>Reference</th><th>Comments mentioning it</th><th>Typical comparison</th><th>Explicit comparisons</th></tr></thead><tbody>{references.map((row) => <tr key={row.reference}><td>{row.reference}</td><td>{number(row.mentions)}</td><td>{row.typical_comparison}</td><td>{number(row.comparisons)}</td></tr>)}</tbody></table></div>}</Load>
    </Panel></section>
    <section className={s.section}><Panel title="Comment evidence" description="Examples are sorted with explicit comparisons first, then recorded likes."><Load resource={data}>{({ examples }) => <div className={s.tableWrap}><table className={s.table}><thead><tr><th>Reference</th><th>Channel</th><th>Comment</th><th>Type</th><th>Likes</th></tr></thead><tbody>{examples.map((row) => <tr key={`${row.reference}-${row.comment_id}`}><td>{row.reference}</td><td>{platform(row.platform)}</td><td dir="auto">{row.comment_text}</td><td>{row.is_comparison ? "Comparison" : "Mention"}</td><td>{number(row.likes)}</td></tr>)}</tbody></table></div>}</Load></Panel></section>
  </CampaignShell>;
}
