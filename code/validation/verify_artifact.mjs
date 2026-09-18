import fs from "node:fs/promises";
import { Workbook } from "@oai/artifact-tool";

const csvText = await fs.readFile("outputs/codex_stance_validation.csv", "utf8");
const workbook = await Workbook.fromCSV(csvText, { sheetName: "Validation" });
const summary = await workbook.inspect({
  kind: "workbook,sheet,table",
  maxChars: 2000,
  tableMaxRows: 2,
  tableMaxCols: 8,
  tableMaxCellChars: 60,
});
console.log(summary.ndjson);
const preview = await workbook.render({
  sheetName: "Validation",
  range: "A1:P20",
  scale: 1,
  format: "png",
});
await fs.writeFile(
  "/tmp/codex_stance_validation_artifact/validation_preview.png",
  new Uint8Array(await preview.arrayBuffer()),
);
