#!/usr/bin/env node
/**
 * gen_pptx.js — Generate the Week 8 presentation (max 10 slides)
 *
 * Usage:  node gen_pptx.js [output.pptx]
 * Requires: npm install pptxgenjs
 *
 * Charts in ./charts/ are embedded if they exist.
 */

const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const OUT = process.argv[2] || "week8-presentation.pptx";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const COLORS = {
  bg: "0F172A",        // dark slate
  card: "1E293B",      // slightly lighter
  accent: "3B82F6",    // blue
  accent2: "10B981",   // emerald
  accent3: "F59E0B",   // amber
  accent4: "EF4444",   // red
  text: "F8FAFC",      // almost white
  muted: "94A3B8",     // slate-400
  white: "FFFFFF",
};

function masterOpts() {
  return { background: { color: COLORS.bg } };
}

function titleText(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.6, y: 0.3, w: "88%", h: 0.7,
    fontSize: 28, bold: true, color: COLORS.text,
    fontFace: "Arial",
    ...opts,
  });
}

function subtitleText(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.6, y: 1.0, w: "88%", h: 0.5,
    fontSize: 16, color: COLORS.muted,
    fontFace: "Arial",
    ...opts,
  });
}

function bodyText(slide, text, opts = {}) {
  slide.addText(text, {
    x: 0.6, y: 1.6, w: "88%", h: 3.8,
    fontSize: 13, color: COLORS.text,
    fontFace: "Arial", valign: "top",
    lineSpacingMultiple: 1.3,
    ...opts,
  });
}

function bulletList(items) {
  return items.map(t => ({
    text: t,
    options: { bullet: { code: "2022" }, fontSize: 13, color: COLORS.text, fontFace: "Arial" },
  }));
}

function addCard(slide, x, y, w, h, title, bullets, color = COLORS.accent) {
  slide.addShape("rect", {
    x, y, w, h,
    fill: { color: COLORS.card },
    rectRadius: 0.1,
    line: { color, width: 1.5 },
  });
  slide.addText(title, {
    x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.4,
    fontSize: 14, bold: true, color, fontFace: "Arial",
  });
  slide.addText(
    bullets.map(t => ({
      text: t,
      options: { bullet: { code: "2022" }, fontSize: 11, color: COLORS.text, fontFace: "Arial" },
    })),
    { x: x + 0.15, y: y + 0.45, w: w - 0.3, h: h - 0.55, valign: "top", lineSpacingMultiple: 1.25 }
  );
}

function tryImage(slide, filePath, opts) {
  const abs = path.resolve(__dirname, filePath);
  if (fs.existsSync(abs)) {
    const data = fs.readFileSync(abs).toString("base64");
    slide.addImage({ data: `image/png;base64,${data}`, ...opts });
    return true;
  }
  slide.addText(`[Chart not found: ${filePath}]`, {
    x: opts.x, y: opts.y, w: opts.w, h: opts.h,
    fontSize: 12, color: COLORS.muted, fontFace: "Arial", align: "center", valign: "middle",
    fill: { color: COLORS.card },
  });
  return false;
}

function footerSlideNum(slide, num, total) {
  slide.addText(`${num} / ${total}`, {
    x: "88%", y: "92%", w: 1, h: 0.3,
    fontSize: 10, color: COLORS.muted, fontFace: "Arial", align: "right",
  });
}

// ---------------------------------------------------------------------------
// Slides
// ---------------------------------------------------------------------------

const pptx = new pptxgen();
pptx.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pptx.author = "Printer Factory Sim";
pptx.subject = "Week 8 — Autonomy and Analysis";

const TOTAL = 10;
let slideNum = 0;

// ── Slide 1: Title ─────────────────────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  s.addText("3D Printer Factory Simulator", {
    x: 0.6, y: 1.5, w: "88%", h: 1.0,
    fontSize: 36, bold: true, color: COLORS.text, fontFace: "Arial",
  });
  s.addText("Week 8 — Autonomy & Analysis", {
    x: 0.6, y: 2.5, w: "88%", h: 0.6,
    fontSize: 22, color: COLORS.accent, fontFace: "Arial",
  });
  s.addText("A discrete-event supply-chain simulation with three autonomous AI agents", {
    x: 0.6, y: 3.3, w: "88%", h: 0.5,
    fontSize: 15, color: COLORS.muted, fontFace: "Arial",
  });
  s.addText("Multi-Agent Coordination  |  Scenario-Driven Stress Testing  |  Emergent Behaviour", {
    x: 0.6, y: 4.8, w: "88%", h: 0.4,
    fontSize: 13, color: COLORS.accent2, fontFace: "Arial",
  });
  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 2: System Architecture ────────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "System Architecture");
  subtitleText(s, "Three independent FastAPI apps orchestrated by a Turn Engine");

  // Turn Engine box (top center)
  s.addShape("rect", { x: 4.5, y: 1.7, w: 4.2, h: 0.8, fill: { color: "4338CA" }, rectRadius: 0.1 });
  s.addText("Turn Engine (orchestrator)", {
    x: 4.5, y: 1.7, w: 4.2, h: 0.8,
    fontSize: 14, bold: true, color: COLORS.white, fontFace: "Arial", align: "center", valign: "middle",
  });

  // Provider
  s.addShape("rect", { x: 0.8, y: 3.3, w: 3.2, h: 1.8, fill: { color: COLORS.card }, rectRadius: 0.1, line: { color: COLORS.accent3, width: 1.5 } });
  s.addText("Provider API :8001", { x: 0.8, y: 3.3, w: 3.2, h: 0.45, fontSize: 13, bold: true, color: COLORS.accent3, fontFace: "Arial", align: "center" });
  s.addText("supplier.db\nStock, Pricing Tiers\nPurchase Orders\nProvider Metrics", { x: 0.9, y: 3.75, w: 3.0, h: 1.2, fontSize: 11, color: COLORS.muted, fontFace: "Arial", align: "center", lineSpacingMultiple: 1.2 });

  // Manufacturer
  s.addShape("rect", { x: 5.0, y: 3.3, w: 3.2, h: 1.8, fill: { color: COLORS.card }, rectRadius: 0.1, line: { color: COLORS.accent, width: 1.5 } });
  s.addText("Manufacturer API :8002", { x: 5.0, y: 3.3, w: 3.2, h: 0.45, fontSize: 13, bold: true, color: COLORS.accent, fontFace: "Arial", align: "center" });
  s.addText("simulator.db\nProduction, Inventory\nSales Orders, BOM\nManufacturer Metrics", { x: 5.1, y: 3.75, w: 3.0, h: 1.2, fontSize: 11, color: COLORS.muted, fontFace: "Arial", align: "center", lineSpacingMultiple: 1.2 });

  // Retailer
  s.addShape("rect", { x: 9.2, y: 3.3, w: 3.2, h: 1.8, fill: { color: COLORS.card }, rectRadius: 0.1, line: { color: COLORS.accent2, width: 1.5 } });
  s.addText("Retailer API :8003", { x: 9.2, y: 3.3, w: 3.2, h: 0.45, fontSize: 13, bold: true, color: COLORS.accent2, fontFace: "Arial", align: "center" });
  s.addText("retailer.db\nCatalog, Customer Orders\nRetailer Stock\nRetailer Metrics", { x: 9.3, y: 3.75, w: 3.0, h: 1.2, fontSize: 11, color: COLORS.muted, fontFace: "Arial", align: "center", lineSpacingMultiple: 1.2 });

  // Arrows from Turn Engine
  s.addShape("line", { x: 5.3, y: 2.5, w: -2.3, h: 0.8, line: { color: COLORS.muted, width: 1.5, dashType: "dash" } });
  s.addShape("line", { x: 6.6, y: 2.5, w: 0, h: 0.8, line: { color: COLORS.muted, width: 1.5, dashType: "dash" } });
  s.addShape("line", { x: 7.9, y: 2.5, w: 2.8, h: 0.8, line: { color: COLORS.muted, width: 1.5, dashType: "dash" } });

  // HTTP arrows between apps
  s.addShape("line", { x: 4.0, y: 4.2, w: 1.0, h: 0, line: { color: COLORS.accent3, width: 2 } });
  s.addText("HTTP", { x: 4.1, y: 3.9, w: 0.8, h: 0.3, fontSize: 9, color: COLORS.muted, fontFace: "Arial", align: "center" });
  s.addShape("line", { x: 8.2, y: 4.2, w: 1.0, h: 0, line: { color: COLORS.accent2, width: 2 } });
  s.addText("HTTP", { x: 8.3, y: 3.9, w: 0.8, h: 0.3, fontSize: 9, color: COLORS.muted, fontFace: "Arial", align: "center" });

  // Key insight
  s.addText("No app touches another's database. All coordination happens through HTTP + shared world state.", {
    x: 0.6, y: 5.7, w: "88%", h: 0.5,
    fontSize: 13, italic: true, color: COLORS.accent, fontFace: "Arial", align: "center",
  });

  // Databases icon labels
  s.addText("3 SQLite DBs  |  3 FastAPI apps  |  1 Turn Engine  |  Scenario-driven events", {
    x: 0.6, y: 6.3, w: "88%", h: 0.4,
    fontSize: 12, color: COLORS.muted, fontFace: "Arial", align: "center",
  });

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 3: Agent — Provider Manager ───────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Agent: Provider Manager");
  subtitleText(s, "skills/provider-manager.md — Manages raw material stock & pricing");

  addCard(s, 0.5, 1.6, 5.8, 2.2, "Decision Framework", [
    "1. Assess — query stock levels & pending orders",
    "2. Restock — replenish products below 50% of starting level",
    "3. Adjust Prices — raise if stock < 30%, lower if > 150%",
    "4. Summarise — structured log for engine capture",
  ], COLORS.accent3);

  addCard(s, 6.8, 1.6, 5.8, 2.2, "Market Signal Response", [
    "supply_modifier < 0.7 → raise prices, conserve stock",
    "demand_modifier > 1.5 → build stock ahead of surge",
    "Max 15% price change per day (gradual adjustments)",
    "Never let stock hit zero if orders are pending",
  ], COLORS.accent3);

  addCard(s, 0.5, 4.2, 12.1, 1.8, "Available CLI Commands", [
    "./provider-cli stock  |  ./provider-cli orders list  |  ./provider-cli catalog",
    "./provider-cli restock <product> <qty>  |  ./provider-cli price set <product> <tier> <price>",
    "Agent NEVER calls day advance — Turn Engine is the sole orchestrator",
  ], COLORS.muted);

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 4: Agent — Manufacturer Manager ───────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Agent: Manufacturer Manager");
  subtitleText(s, "skills/manufacturer-manager.md — Production planning & material procurement");

  addCard(s, 0.5, 1.6, 5.8, 2.5, "Decision Framework (6 steps)", [
    "1. Assess — day, wallet, stock, capacity, sales orders",
    "2. Identify Bottlenecks — compare BOM vs inventory",
    "3. Release Production — prioritize older orders first",
    "4. Plan Material Orders — bulk buy for tier discounts",
    "5. Adjust Pricing — raise if wallet < 3000",
    "6. Report — structured summary for logging",
  ], COLORS.accent);

  addCard(s, 6.8, 1.6, 5.8, 2.5, "Key Constraints", [
    "Daily production capacity: 10 units (configurable)",
    "Must check wallet before ordering materials",
    "Must check supplier stock before placing PO",
    "Tier pricing: 10+ = -10%, 50+ = -18%, 100+ = -25%",
    "Materials reserved on release, consumed on completion",
  ], COLORS.accent);

  addCard(s, 0.5, 4.5, 12.1, 1.5, "Market Signal Response", [
    "demand_modifier > 1.0 → keep stock ready, consider price increases",
    "demand_modifier < 1.0 → conserve cash, reduce orders, avoid overproduction",
  ], COLORS.muted);

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 5: Agent — Retail Manager ─────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Agent: Retail Manager");
  subtitleText(s, "skills/retail-manager.md — Customer fulfillment & pricing strategy");

  addCard(s, 0.5, 1.6, 5.8, 2.2, "Decision Framework", [
    "1. Fulfill — ship from stock or backorder each pending order",
    "2. Reorder — purchase from manufacturer if stock < 3 days demand",
    "3. Price — raise 5% if stock low, lower 5% if piling up",
    "4. Summarise — orders fulfilled, backordered, purchases placed",
  ], COLORS.accent2);

  addCard(s, 6.8, 1.6, 5.8, 2.2, "Key Rules", [
    "NEVER leave customer orders in 'pending' status",
    "Retail price MUST be > manufacturer wholesale + 20%",
    "Reorder enough to cover ~5 days of expected demand",
    "Backordered orders trigger extra reorder quantity",
  ], COLORS.accent2);

  addCard(s, 0.5, 4.2, 12.1, 1.8, "Market Signal Response", [
    "demand_modifier > 1.5 → place larger purchase orders now, hold or raise prices",
    "demand_modifier < 0.8 → slow reorders, consider cutting prices 5%",
    "price_sensitivity = 'high' → be cautious raising prices, customers are shopping around",
  ], COLORS.muted);

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 6: Scenario Design ────────────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Scenario Design");
  subtitleText(s, "Two scenarios: calm baseline vs. volatile holiday rush");

  // Calm market card
  addCard(s, 0.5, 1.6, 5.8, 2.6, "Calm Market (Control)", [
    "25 days, stable demand (mean=4, var=1)",
    "demand_modifier = 1.0 throughout",
    "supply_modifier = 1.0 throughout",
    "Purpose: establish baseline agent behaviour",
    "No disruptions — tests steady-state decisions",
  ], COLORS.accent2);

  // Holiday rush card
  addCard(s, 6.8, 1.6, 5.8, 2.6, "Holiday Rush (Volatile)", [
    "Days 1-10: Normal (demand=1.0x, supply=1.0x)",
    "Days 11-13: Black Friday (demand=3.0x, price-sensitive)",
    "Days 14-20: Chip Shortage (supply=0.4x, lead time=2.0x)",
    "Days 18-25: Christmas (demand=2.5x, supply=0.6x)",
    "Days 18-20: COMPOUND (demand=3.75x, supply=0.24x)",
  ], COLORS.accent4);

  // Event timeline visualization
  s.addShape("rect", { x: 0.5, y: 4.7, w: 12.1, h: 1.6, fill: { color: COLORS.card }, rectRadius: 0.1 });
  s.addText("Holiday Rush Timeline", { x: 0.7, y: 4.75, w: 4, h: 0.35, fontSize: 12, bold: true, color: COLORS.text, fontFace: "Arial" });

  // Timeline bar
  const tlY = 5.3;
  const tlX = 1.0;
  const dayW = 0.42;

  // Day labels
  for (let d = 1; d <= 25; d++) {
    s.addText(`${d}`, {
      x: tlX + (d - 1) * dayW, y: tlY + 0.55, w: dayW, h: 0.25,
      fontSize: 8, color: COLORS.muted, fontFace: "Arial", align: "center",
    });
  }

  // Normal (1-10): grey
  s.addShape("rect", { x: tlX, y: tlY, w: dayW * 10, h: 0.25, fill: { color: "475569" }, rectRadius: 0.05 });
  s.addText("Normal", { x: tlX, y: tlY - 0.25, w: dayW * 10, h: 0.25, fontSize: 9, color: "475569", fontFace: "Arial", align: "center" });

  // Black Friday (11-13): amber
  s.addShape("rect", { x: tlX + dayW * 10, y: tlY, w: dayW * 3, h: 0.25, fill: { color: COLORS.accent3 }, rectRadius: 0.05 });
  s.addText("BF", { x: tlX + dayW * 10, y: tlY - 0.25, w: dayW * 3, h: 0.25, fontSize: 9, color: COLORS.accent3, fontFace: "Arial", align: "center" });

  // Chip shortage (14-20): red
  s.addShape("rect", { x: tlX + dayW * 13, y: tlY + 0.28, w: dayW * 7, h: 0.22, fill: { color: COLORS.accent4 }, rectRadius: 0.05 });
  s.addText("Chip Shortage", { x: tlX + dayW * 13, y: tlY - 0.25, w: dayW * 7, h: 0.25, fontSize: 9, color: COLORS.accent4, fontFace: "Arial", align: "center" });

  // Christmas (18-25): green
  s.addShape("rect", { x: tlX + dayW * 17, y: tlY, w: dayW * 8, h: 0.25, fill: { color: COLORS.accent2 }, rectRadius: 0.05 });
  s.addText("Christmas", { x: tlX + dayW * 17, y: tlY - 0.5, w: dayW * 8, h: 0.25, fontSize: 9, color: COLORS.accent2, fontFace: "Arial", align: "center" });

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 7: Live Demo ──────────────────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Live Demo");
  subtitleText(s, "Running 2-3 simulated days with all three agents");

  s.addText("python turn_engine.py config/sim.json scenarios/holiday-rush.json 25", {
    x: 1.5, y: 2.2, w: 10, h: 0.6,
    fontSize: 16, color: COLORS.accent2, fontFace: "Courier New",
    fill: { color: COLORS.card },
    align: "center", valign: "middle",
    rectRadius: 0.1,
  });

  addCard(s, 0.5, 3.2, 3.8, 2.5, "What to Watch", [
    "Agent decisions printed per turn",
    "Market signals passed to each agent",
    "Day summary: orders / fulfilled / backordered",
    "Wallet changes and inventory shifts",
  ], COLORS.accent);

  addCard(s, 4.8, 3.2, 3.8, 2.5, "Emergent Behaviour", [
    "Bullwhip effect: demand amplified upstream",
    "Price wars during low demand",
    "Stockout cascades across the chain",
    "Coordination WITHOUT direct communication",
  ], COLORS.accent3);

  addCard(s, 9.1, 3.2, 3.6, 2.5, "Dashboard", [
    "localhost:8002 — full React SPA",
    "Real-time SVG charts",
    "Scenario timeline overlay",
    "Event logs from all 3 apps",
  ], COLORS.accent2);

  s.addText("The demo is the most important part. Have a plan for what to do if agents stall.", {
    x: 0.6, y: 6.2, w: "88%", h: 0.4,
    fontSize: 12, italic: true, color: COLORS.muted, fontFace: "Arial", align: "center",
  });

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 8: Chart — Inventory over Time ────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Results: Inventory Over Time");

  tryImage(s, "charts/inventory_test.png", { x: 0.5, y: 1.3, w: 6.0, h: 4.0 });

  addCard(s, 6.8, 1.3, 5.8, 4.0, "Interpretation", [
    "Three lines: parts stock (manufacturer), finished-printer stock (manufacturer), printer stock (retailer)",
    "Look for: stock drawdowns during Black Friday (days 11-13), recovery patterns after the spike",
    "Chip shortage (days 14-20) should cause parts stock to plateau or drop as supply is constrained",
    "Christmas overlap (days 18-20) is the stress peak — compound demand 3.75x with supply at 0.24x",
    "Did the manufacturer build stock ahead of Black Friday? If not, stockouts cascade downstream",
  ], COLORS.accent);

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 9: Chart — Prices + Fulfillment ───────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Results: Prices & Order Fulfillment");

  tryImage(s, "charts/prices_test.png", { x: 0.3, y: 1.3, w: 5.8, h: 2.7 });
  tryImage(s, "charts/fulfillment_test.png", { x: 0.3, y: 4.2, w: 5.8, h: 2.7 });

  addCard(s, 6.5, 1.3, 6.2, 2.7, "Prices Interpretation", [
    "Three lines: provider part price, manufacturer wholesale, retailer retail",
    "Prices should rise during shortage (days 14-20) as agents react to supply_modifier < 0.7",
    "Did prices stabilise or oscillate? Oscillation = agents overreacting to signals",
    "Price sensitivity during Black Friday: did the retailer hold prices despite high demand?",
  ], COLORS.accent3);

  addCard(s, 6.5, 4.2, 6.2, 2.7, "Fulfillment Interpretation", [
    "Daily bars: orders placed vs fulfilled vs backordered",
    "Backorder spikes indicate stockouts — whose decision was the root cause?",
    "Compare calm scenario (near-100% fulfillment) vs holiday rush (gaps expected)",
    "Bullwhip moment: demand variance amplified upstream through the chain",
  ], COLORS.accent2);

  footerSlideNum(s, slideNum, TOTAL);
}

// ── Slide 10: Reflection ────────────────────────────────────────────────────
{
  const s = pptx.addSlide(masterOpts());
  slideNum++;
  titleText(s, "Reflection & Lessons Learned");

  addCard(s, 0.5, 1.4, 5.8, 2.3, "What Worked", [
    "Three-DB isolation: clean boundaries, no coupling",
    "Skill-based agent design: version-controlled, testable",
    "Scenario-driven testing: reproducible stress conditions",
    "Event-sourced logging: full audit trail for analysis",
  ], COLORS.accent2);

  addCard(s, 6.8, 1.4, 5.8, 2.3, "Challenges", [
    "Agents can make bad calls that cascade into crises",
    "Skill ambiguities revealed mid-run (tuning needed)",
    "Compound events (3.75x demand + 0.24x supply) are brutal",
    "Observability is crucial — without metrics, analysis is impossible",
  ], COLORS.accent4);

  addCard(s, 0.5, 4.1, 12.1, 1.8, "Key Takeaway", [
    "Emergence is the feature: coordination happens through world state, not direct communication",
    "Deterministic software handles execution; LLMs handle strategy; well-defined interfaces keep everything auditable",
    "The hardest part was not any single component — it was keeping your head across all of them",
    "This architecture mirrors real autonomous systems: Uber surge pricing, Amazon warehouse robots, MMO economies",
  ], COLORS.accent);

  s.addText("This is not a toy. This is the shape of real autonomous business systems.", {
    x: 0.6, y: 6.3, w: "88%", h: 0.4,
    fontSize: 14, bold: true, color: COLORS.accent, fontFace: "Arial", align: "center",
  });

  footerSlideNum(s, slideNum, TOTAL);
}

// ---------------------------------------------------------------------------
// Write
// ---------------------------------------------------------------------------

pptx.writeFile({ fileName: OUT }).then(() => {
  console.log(`Presentation saved → ${OUT}  (${slideNum} slides)`);
}).catch(err => {
  console.error("Error generating PPTX:", err);
  process.exit(1);
});
