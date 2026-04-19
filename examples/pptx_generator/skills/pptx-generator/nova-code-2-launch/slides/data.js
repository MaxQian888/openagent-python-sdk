const theme = {
  primary: "0C1E33",
  secondary: "174A7A",
  accent: "34C3FF",
  light: "DFF7FF",
  bg: "07111E"
};

module.exports = {
  theme,
  product: "Nova Code 2.0",
  subtitle: "AI Coding Assistant Release",
  launchLabel: "Internal launch / Product team",
  releaseThesis:
    "Nova Code 2.0 shifts the assistant from isolated code generation to a capability release that helps product teams understand requests, compose implementation paths, and close the verification loop before handoff.",
  highlightChips: [
    "Spec aware generation",
    "Verification first loops",
    "Context continuity across tasks"
  ],
  heroMetrics: [
    { label: "Handoff clarity", value: "+41%" },
    { label: "Issue surfacing", value: "3.2x" },
    { label: "Multi-file flow", value: "10-step" }
  ],
  releasePillars: [
    {
      tag: "01",
      title: "Plan before patch",
      body: "Turn release requests into shaped work instead of raw prompt-to-code jumps."
    },
    {
      tag: "02",
      title: "Verify before handoff",
      body: "Make lint, tests, and build outputs part of the product surface."
    },
    {
      tag: "03",
      title: "Carry context forward",
      body: "Keep task state, repo conventions, and release intent coherent across the session."
    }
  ],
  capabilities: [
    {
      tag: "A",
      title: "Spec-to-code orchestration",
      body: "Translate product asks into files, tasks, code paths, and release-shaped deliverables."
    },
    {
      tag: "B",
      title: "Verification loops",
      body: "Run focused checks, surface failures early, and keep quality signals visible."
    },
    {
      tag: "C",
      title: "Context continuity",
      body: "Preserve project truth, current intent, and task-level state without dropping seams."
    },
    {
      tag: "D",
      title: "Team-ready output",
      body: "Package work as explainable artifacts instead of raw code fragments."
    }
  ],
  orchestrationSteps: [
    {
      tag: "01",
      title: "Capture request",
      body: "Pin the product ask, release scope, and success criteria before implementation."
    },
    {
      tag: "02",
      title: "Shape the plan",
      body: "Map files, slide structure, and execution checkpoints before touching output."
    },
    {
      tag: "03",
      title: "Compose changes",
      body: "Build content in modules so each deliverable remains inspectable and reusable."
    },
    {
      tag: "04",
      title: "Validate the artifact",
      body: "Run the real command path and extract the result back into reviewable text."
    }
  ],
  verificationBars: [
    { label: "Lint alignment", ratio: 1.0, value: "100%", color: "34C3FF" },
    { label: "Targeted tests", ratio: 0.94, value: "94%", color: "5ED4FF" },
    { label: "Build confidence", ratio: 0.89, value: "89%", color: "7CE4FF" }
  ],
  continuityLayers: [
    { title: "User intent", body: "What the team is trying to ship now." },
    { title: "Repository truth", body: "What the codebase and current constraints actually allow." },
    { title: "Task memory", body: "What was already decided in this release thread." },
    { title: "Verification state", body: "Which checks passed, failed, or still need proof." }
  ],
  workflowSteps: [
    { tag: "01", title: "Request", body: "Feature ask or release note arrives." },
    { tag: "02", title: "Frame", body: "Scope and target files are locked." },
    { tag: "03", title: "Build", body: "Content and code are generated in bounded units." },
    { tag: "04", title: "Check", body: "Commands prove the artifact." },
    { tag: "05", title: "Hand off", body: "Team gets a reviewable, explainable output." }
  ],
  comparisonRows: [
    { label: "Primary output", oldValue: "Code fragments", newValue: "Release-shaped work units" },
    { label: "Request handling", oldValue: "Prompt to patch", newValue: "Intent to plan to patch" },
    { label: "Quality proof", oldValue: "Optional follow-up", newValue: "Built into the default flow" },
    { label: "Context model", oldValue: "Turn-local memory", newValue: "Thread-level continuity" },
    { label: "Team fit", oldValue: "Single-user acceleration", newValue: "Product-team delivery surface" }
  ],
  scenarios: [
    {
      tag: "01",
      title: "Complex feature build",
      body: "Best when the team needs plan, implementation, and validation in one release thread."
    },
    {
      tag: "02",
      title: "Regression repair",
      body: "Best when fast root-cause isolation must be paired with proof before re-ship."
    },
    {
      tag: "03",
      title: "Multi-file refactor",
      body: "Best when scope crosses components, config, and verification surfaces."
    },
    {
      tag: "04",
      title: "Pre-release confidence",
      body: "Best when the team needs a last-mile quality pass before handoff or demo."
    }
  ],
  impactMetrics: [
    {
      label: "Iteration speed",
      value: "3.2x",
      body: "Verification and build proof move earlier in the loop."
    },
    {
      label: "Handoff loss",
      value: "-34%",
      body: "The output stays explainable for reviewers and adjacent teammates."
    },
    {
      label: "Plan clarity",
      value: "+41%",
      body: "The session holds onto scope and deliverable structure more reliably."
    }
  ],
  nextActions: [
    "Pilot Nova Code 2.0 on one complex sprint item.",
    "Track verification time saved against the 1.x workflow.",
    "Promote the release flow into the default internal playbook."
  ]
};
