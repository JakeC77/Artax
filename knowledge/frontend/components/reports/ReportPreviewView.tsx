import { useState, useEffect, useCallback } from "react";
import { Box, Typography, CircularProgress, Divider } from "@mui/material";
import { fetchReportById, fetchReportTemplateById } from "../../services/graphql";
import ReportBlockRenderer from "./preview/ReportBlockRenderer";
import SourcesList from "./preview/SourcesList";
import type { Report, ReportBlock, ReportTemplate } from "../../types/reports";

// Parse layoutHints to get width fraction
function parseWidth(layoutHints: string | null): number {
  if (!layoutHints) return 1;

  try {
    const hints = JSON.parse(layoutHints);
    const width = hints.width;

    if (width === "full") return 1;
    if (typeof width === "string" && width.includes("/")) {
      const [numerator, denominator] = width.split("/").map(Number);
      return numerator / denominator;
    }
    return 1;
  } catch {
    return 1;
  }
}

// Group blocks into rows based on their widths
function groupBlocksIntoRows(blocks: ReportBlock[]): ReportBlock[][] {
  const rows: ReportBlock[][] = [];
  let currentRow: ReportBlock[] = [];
  let currentRowWidth = 0;

  for (const block of blocks) {
    const width = parseWidth(block.layoutHints);

    if (width >= 1) {
      if (currentRow.length > 0) {
        rows.push([...currentRow]);
        currentRow = [];
        currentRowWidth = 0;
      }
      rows.push([block]);
      continue;
    }

    if (currentRowWidth + width <= 1 + 0.001) {
      currentRow.push(block);
      currentRowWidth += width;
    } else {
      if (currentRow.length > 0) {
        rows.push([...currentRow]);
      }
      currentRow = [block];
      currentRowWidth = width;
    }
  }

  if (currentRow.length > 0) {
    rows.push([...currentRow]);
  }

  return rows;
}

interface ReportPreviewViewProps {
  reportId: string;
}

export default function ReportPreviewView({
  reportId,
}: ReportPreviewViewProps) {
  const [report, setReport] = useState<Report | null>(null);
  const [template, setTemplate] = useState<ReportTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const reportData = await fetchReportById(reportId);
      if (!reportData) {
        setError("Report not found");
        setLoading(false);
        return;
      }
      setReport(reportData);

      if (reportData.templateId && reportData.templateVersion != null) {
        const templateData = await fetchReportTemplateById(
          reportData.templateId,
          reportData.templateVersion,
        );
        setTemplate(templateData);
      }
    } catch (e: any) {
      setError(e?.message || "Failed to load report");
    } finally {
      setLoading(false);
    }
  }, [reportId]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  if (loading) {
    return (
      <Box
        sx={{
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          minHeight: 400,
        }}
      >
        <CircularProgress />
      </Box>
    );
  }

  if (error || !report) {
    return (
      <Box sx={{ p: 3, textAlign: "center" }}>
        <Typography color="error">{error || "Report not found"}</Typography>
      </Box>
    );
  }

  // Template is optional - we can still render the report without it
  void template;

  return (
    <Box>
      {/* Report Header */}
      <Box
        sx={{ mb: 4, pb: 3, borderBottom: "2px solid", borderColor: "divider" }}
      >
        <Typography variant="h3" sx={{ fontWeight: 700, mb: 1 }}>
          {report.title}
        </Typography>
        <Box sx={{ display: "flex", gap: 2, flexWrap: "wrap", mt: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Status: {report.status}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Type: {report.type}
          </Typography>
        </Box>
      </Box>

      {/* Sections */}
      {report.sections
        .sort((a, b) => a.order - b.order)
        .map((section) => {
          const sortedBlocks = [...section.blocks].sort(
            (a, b) => a.order - b.order,
          );
          const blockRows = groupBlocksIntoRows(sortedBlocks);

          return (
            <Box key={section.reportSectionId} sx={{ mb: 5 }}>
              <Typography variant="h4" sx={{ fontWeight: 600, mb: 3 }}>
                {section.header}
              </Typography>

              {blockRows.map((row, rowIndex) => (
                <Box
                  key={`row-${rowIndex}`}
                  sx={{
                    display: "grid",
                    gridTemplateColumns: "repeat(12, 1fr)",
                    gap: 2,
                    mb: 2,
                  }}
                >
                  {row.map((blockItem) => {
                    const width = parseWidth(blockItem.layoutHints);
                    const gridSpan = width >= 1 ? 12 : Math.round(width * 12);
                    return (
                      <Box
                        key={blockItem.reportBlockId}
                        sx={{
                          gridColumn: `span ${gridSpan}`,
                        }}
                      >
                        <ReportBlockRenderer block={blockItem} sources={report.sources} />
                      </Box>
                    );
                  })}
                </Box>
              ))}

              {section.reportSectionId !==
                report.sections[report.sections.length - 1]
                  ?.reportSectionId && <Divider sx={{ mt: 4 }} />}
            </Box>
          );
        })}

      {/* Sources */}
      <SourcesList sources={report.sources} />
    </Box>
  );
}
