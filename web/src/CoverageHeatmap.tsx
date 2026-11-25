import { AlertCircle } from "lucide-react";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type CoverageResponse } from "./api";

const RANGES = [30, 90, 250];

const statusLabels: Record<string, string> = {
  complete: "完整",
  missing: "缺失",
  failed: "采集失败",
  abnormal: "文件异常",
  pending: "待采集",
};

export default function CoverageHeatmap({ onOpen, refreshToken = 0 }: { onOpen: (id: string) => void; refreshToken?: number }) {
  const [days, setDays] = useState(90);
  const [data, setData] = useState<CoverageResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async (range: number) => {
    setLoading(true);
    setError(null);
    try {
      setData(await api.getCoverage(range));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "无法加载覆盖数据");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(days);
  }, [days, load, refreshToken]);

  const months = useMemo(() => groups(data?.dates ?? []), [data]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    const frame = window.requestAnimationFrame(() => {
      container.scrollLeft = container.scrollWidth;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [data, days]);

  return (
    <section className="panel coverage-panel">
      <div className="panel-toolbar">
        <div>
          <h2>覆盖热力图</h2>
          <span>{data ? `${data.datasets.length} 个日分区数据集 · ${data.dates.length} 个交易日` : "加载中"}</span>
        </div>
        <div className="coverage-tools">
          <div className="range-switch">
            {RANGES.map((range) => (
              <button
                key={range}
                type="button"
                className={range === days ? "active" : ""}
                onClick={() => setDays(range)}
              >
                近 {range} 天
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <div className="form-error"><AlertCircle size={16} />{error}</div>}

      <div className="coverage-legend">
        {Object.entries(statusLabels).map(([key, label]) => (
          <span key={key}><i className={`cell-${key}`} />{label}</span>
        ))}
        <em>点击格子进入数据集详情</em>
      </div>

      {loading ? (
        <div className="state-box"><div className="loader" /><p>正在汇总覆盖情况…</p></div>
      ) : !data || !data.datasets.length ? (
        <div className="state-box empty-state"><strong>没有可展示的日分区数据集</strong><p>只有绑定了交易日历的数据集才会出现在热力图里。</p></div>
      ) : (
        <div className="coverage-body">
          <div className="coverage-names">
            <div className="coverage-names-spacer" />
            {data.datasets.map((dataset) => (
              <div className="coverage-name" key={dataset.dataset_id} title={dataset.dataset_id}>
                <strong>{dataset.display_name}</strong>
                <small>{summaryText(dataset.summary)}</small>
              </div>
            ))}
          </div>
          <div className="coverage-scroll" ref={scrollRef}>
            <div
              className="coverage-grid"
              style={{ gridTemplateColumns: `repeat(${data.dates.length}, 13px)` }}
            >
              <div className="coverage-months" style={{ gridColumn: `span ${data.dates.length}` }}>
                {months.map((month) => (
                  <span
                    key={month.key}
                    className="coverage-month"
                    style={{ width: `${month.span * 15 - 2}px` }}
                  >
                    {month.label}
                  </span>
                ))}
              </div>
              {data.datasets.map((dataset) => (
                <Fragment key={dataset.dataset_id}>
                  {data.dates.map((day) => {
                    const status = dataset.cells[day] ?? "none";
                    const detail = dataset.details[day];
                    const tooltip = [
                      `${dataset.display_name} · ${day}`,
                      statusLabels[status] ?? "未采集",
                      detail?.row_count !== null && detail?.row_count !== undefined ? `${detail.row_count.toLocaleString()} 行` : "",
                      detail?.error ?? "",
                    ].filter(Boolean).join("\n");
                    return (
                      <button
                        key={day}
                        type="button"
                        className={`coverage-cell cell-${status}`}
                        title={tooltip}
                        onClick={() => onOpen(dataset.dataset_id)}
                      />
                    );
                  })}
                </Fragment>
              ))}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}

function summaryText(summary: Record<string, number> | undefined) {
  const missing = summary?.missing ?? 0;
  const failed = summary?.failed ?? 0;
  const abnormal = summary?.abnormal ?? 0;
  if (!missing && !failed && !abnormal) return "无缺口";
  return [
    missing ? `缺 ${missing}` : "",
    failed ? `失败 ${failed}` : "",
    abnormal ? `异常 ${abnormal}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

function groups(dates: string[]) {
  const result: Array<{ key: string; label: string; span: number }> = [];
  for (const value of dates) {
    const month = value.slice(0, 7);
    const last = result[result.length - 1];
    if (last && last.key === month) {
      last.span += 1;
    } else {
      result.push({ key: month, label: `${Number(value.slice(5, 7))}月`, span: 1 });
    }
  }
  return result;
}
