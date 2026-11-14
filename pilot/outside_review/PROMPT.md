# Review request: stimulus texts for an experiment with language-model agents

The attached file, MATERIALS.md, holds everything you need. Please read all of it before answering.

**What these texts are.** A behavioral experiment places a language-model agent on a simulated team as the last of ten workers to act in a round. A manager has cut one worker's budget. Earlier workers' orders have been withheld, either by their own choice or by an automatic lottery, and if enough orders are withheld, the platform restores the cut. The agent decides whether to withhold its own order, which costs it a fee. Conditions vary whether the agent's withholding decides the outcome, whether the earlier withholdings were chosen or came from the lottery, whether the cut was retaliatory or authorized, and the size of the fee. In a separate reward round, the agent may transfer credits to a coworker whose order was withheld by choice or by the lottery. Consequences are real inside the environment: credits buy attempts at a scored task afterward.

The study maps what a refusal responds to: the merits of the case, a standing allegiance to coworkers or to the manager, or features that should not matter. It does not treat refusal as good or bad.

**What you are reviewing.** The texts the agent reads, in four versions written independently from the same brief: two in workplace language and two in neutral language. Code inserts every number and every condition-specific phrase; the writers wrote only the surrounding words. Part 1 of the materials is the brief (the facts every version must convey, and the rules for how), Part 2 lists the conditions, and Part 3 shows every message each version produces.

**Please assess:**

1. **Fidelity.** Any fact in the brief missing from a version, and anything stated or implied that the brief does not contain.
2. **Tilt.** Wording that makes one option more natural, principled, costly, expected or vivid; asymmetries between paired texts (the two options, the two cut paragraphs, the two origin lines, R1 against R2).
3. **Manipulation strength.** Whether each manipulation reads clearly enough to work, and no louder than it should: the lottery's "no choice"; the threshold and count (can the agent tell whether its act decides the outcome without being told?); retaliatory against authorized; the raised fee; the private payment.
4. **Comprehension.** Wording that could lead a careful reader to a wrong answer on the comprehension questions.
5. **Frame.** Whether the neutral versions are free of workplace and labor-dispute connotations, and whether the workplace versions add any script beyond the facts.
6. **Comparability.** Differences between versions, other than frame, that could change behavior.
7. **Demand and refusal risks.** Anything that signals this is a test or what answer is expected, or that might lead a model to refuse or to treat the scenario as role-play.

Please do not redesign the study or critique the protocol beyond what the texts show. If a design choice visible in the texts seems harmful, flag it once, briefly.

**Answer format.** A ranked list of issues, most serious first. For each: severity (high: could change comprehension or tilt the choice; medium; low), the version or versions, the exact quoted text, what is wrong and why it matters, and a one-line fix. Then a short list of what holds up and should not change. Then a one-paragraph verdict: are these four versions fit for a pilot, and if not, what must change first? Say what you could not verify.
