# Presentation Content Outline

The stable slides can be drafted before the five-day gate. The model-selection and validation
section is now drafted in English, with a separate Chinese speaker script. Result slides remain
unfilled until the preliminary and formal evaluation artifacts exist. This outline defines the
full story and the evidence required for each slide.

| Slide | Plain-language headline | Evidence or visual | Speaker objective |
|---|---|---|---|
| 1 | Where will a bike be available one hour from now? | Product screenshot and one-sentence objective | Establish the user problem immediately. |
| 2 | Empty and full stations are a timing problem | Map showing live risk distribution | Explain why station-level forecasting matters. |
| 3 | No history existed, so collection was part of the model | Five-day collection timeline | Show ownership of the full data problem. |
| 4 | Every raw response remains replayable | Pipeline architecture and failure boundaries | Demonstrate reliability and auditability. |
| 5 | The target is simple; aligning it correctly is not | `t` to `t+60m` timeline with tolerance | Explain label construction without jargon. |
| 6 | We only use information known at prediction time | Feature availability timeline | Make leakage prevention understandable. |
| 7 | Prior research changed four design decisions | Evidence-to-decision matrix with concise citations | Show what was adopted, deferred, and why the architecture remains appropriate. |
| 8 | Several models competed across future time windows | Rolling-origin fold diagram and model table | Prove model selection was fair. |
| 9 | The winning model beat a strong same-as-now baseline | Final holdout MAE/RMSE chart | State the main quantitative result. |
| 10 | Performance differs by time, weather and station | Subgroup error panels | Surface operational weaknesses, not only averages. |
| 11 | Recent flow, time and location drive forecasts | SHAP summary with plain labels | Explain global drivers. |
| 12 | What if rain starts within the next hour? | Controlled scenario comparison | Show one useful model-response experiment. |
| 13 | The application turns a model into a decision tool | Live product flow | Demonstrate search, map, uncertainty and explanation. |
| 14 | Five days proves the pipeline, not every season | Honest limitation table | Show judgment and avoid overstating evidence. |
| 15 | Another month would improve calibration and operations | Prioritized roadmap | End with concrete next steps and business value. |

## Writing rules for the final deck

- One conclusion per slide.
- Slide titles state the conclusion, not the topic.
- Technical terms are explained in ordinary English on first use.
- Every metric names its time split and sample period.
- Planned work is never phrased as completed work.
- Charts show units, sample sizes, baseline, and direction of improvement.
- Detailed algorithms and schemas belong in the appendix or technical documentation.

