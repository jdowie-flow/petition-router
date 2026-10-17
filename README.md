# Petition Router

Can a language model tell which government department should respond to a petition to Parliament?

When a petition on [petition.parliament.uk](https://petition.parliament.uk) passes 10,000 signatures, the government responds, and the site's staff tag the petition with the department responsible. Those tags are a few hundred real routing decisions, made by people, to test models against.

This project asks models to route those petitions, and answers three questions:

- How often does a model pick the department a petition is tagged with?
- Is it better than simple word matching? That is a TF-IDF classifier with logistic regression, the cheap option a model has to beat.
- Is it better than a person? I routed 100 of the same petitions by hand before seeing any answers.

## Results

Both Claude models were far more accurate than word matching, and than me.

- **They pick a tagged department for most petitions.** Claude Sonnet 5.5 got 87% of the 396 petitions right and Claude Haiku 5.5 got 83%, and neither ever named a department that wasn't on the list. Always answering the Department of Health and Social Care, the most common department, would get 16%.
- **Word matching gets 40%.** It does well on the biggest departments, with 98% on Health and Social Care, but gets none right in 11 of the 18, including every department with 20 petitions or fewer, most likely because it has too few examples of those to learn from.
- **Both models beat me, and were faster.** On the 100 petitions I labelled, I got 60%, against 88% for Sonnet and 81% for Haiku, and both gaps are clear. The models took a median of about 1.5 seconds per petition, and I took 3.6. I'm not an expert at this, so someone who routes correspondence for a living might do better.
- **Haiku is nearly as accurate as Sonnet, at a fourteenth of the cost:** $0.14 per 1,000 petitions, against $2.00.
- **Haiku's changes of mind flag likely mistakes.** Asked the same thing again, it changed 5% of its answers, and with the list of departments reversed it changed 6%, so the order of the list barely sways it. It gave the same answer all three times for 363 of the 396 petitions and was right on 87% of those, against 42% of the other 33. Answers that change between runs are the ones worth a person checking.
- **There is no sign of the models remembering answers, though only a big effect would show.** Both models were trained on data up to the end of June 2026. Sonnet got 87% of the 325 petitions answered by then and 86% of the 71 answered after. Its lead over word matching, which cannot have seen any of them, was the same either side, and so was Haiku's, give or take a point. With only 71 petitions after the cutoff, though, a difference of up to about 15 points can't be ruled out.

The tags are a strict test. Some petitions could reasonably go to a department that isn't tagged, so some "wrong" answers, mine and the models', may be defensible. See [Known problems](#known-problems).

All 396 petitions:

| Routed by | Right department | 95% interval | Compared with word matching | Unusable replies | Cost per 1,000 | Median time |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| Claude Sonnet 5.5 | 87% | 84% to 90% | +47 points (+42 to +53) | 0 | $2.00 | 1.5 s |
| Claude Haiku 5.5 | 83% | 80% to 87% | +43 points (+38 to +49) | 0 | $0.14 | 1.4 s |
| Word matching (TF-IDF) | 40% | 35% to 45% |  | 0 | $0.00 | under 1 ms |

The 100 petitions I labelled:

| Routed by | Right department | 95% interval | Compared with me | Same answer as me |
| --- | ---: | --- | --- | ---: |
| Me | 60% | 50% to 69% |  |  |
| Claude Sonnet 5.5 | 88% | 81% to 94% | +28 points (+18 to +39) | 58% |
| Claude Haiku 5.5 | 81% | 73% to 88% | +21 points (+10 to +32) | 55% |
| Word matching (TF-IDF) | 38% | 28% to 48% | −22 points (−33 to −11) | 39% |

## How it works

The download takes every petition in the current Parliament that has a government response. It keeps the title, background and details, and drops the petitioner's name and the response itself, which would give the department away. Petitions with a response but no department tag are left out, and the download says how many.

Labelling comes first. A first page sets out the rules, such as not looking anything up or using AI tools, and the time they were agreed to is saved with the labels. The labelling page then shows 100 petitions picked at random, with the same list of departments the models get, and no answers. It times each one, says so on the first page, and stops the clock while the tab is in the background. You can go back and change a label until the last one is saved. Then the labels are fixed. The models only run after that, and the results page stays closed until then.

A model gets the petition and the list of departments, A to Z, and replies with one department and a one-sentence reason. It's right if it picks any department the petition is tagged with. A reply that does not name a listed department counts as wrong, and is kept so you can see what the model said. Answers are saved as they arrive, so a run that stops part way carries on from there next time.

The TF-IDF (term frequency–inverse document frequency) baseline is built with scikit-learn and scored with 5-fold cross-validation, so every petition is predicted by a model that never saw it. Petitions that got the same government response, usually near-duplicates, are kept in the same fold.

The accuracy figures in the two main tables come with 95% intervals from resampling the petitions 2,000 times. Petitions that got the same response are resampled together, because they are not independent. Each model is compared with the TF-IDF baseline, and with my labels, on the same petitions, so the difference is measured directly instead of being read off two overlapping intervals.

Claude Haiku 5.5 is asked three times: twice with the departments A to Z and once Z to A. The repeat measures how much its answers vary on their own. If reversing the list changes more of them than that, the order is swaying it. Petitions that get the same answer all three times are the ones a model might route without a person checking, so the results show how often it's right on those and on the rest.

Anthropic publishes the last month of each model's training data. A model may have seen the responses published by then, so the results compare its accuracy on petitions answered before and after that month. TF-IDF, which cannot have seen any of them, is the yardstick: if a model's lead over it is clearly bigger before the cutoff than after, the model may be remembering answers.

## Running it

You need [uv](https://docs.astral.sh/uv/), Node.js 22.12 or later, and an [Anthropic API key](https://console.anthropic.com) with a few dollars of credit.

```sh
make
```

This installs everything, downloads the petitions and opens the labelling page in your browser. Label all 100, which can take up to an hour. To stop part way, press Ctrl+C in the terminal, and run `make` again to carry on.

When you save the last label, `make` carries on in the terminal. The first time, it asks you to put your API key in the `.env` file it creates, then run `make` again. It runs the TF-IDF baseline, Claude Haiku 5.5 three times and Claude Sonnet 5.5 once, which takes about 15 minutes, and opens the results. Running `make` after that just opens the results. The results page can be saved as a PDF, and every answer can be downloaded as a spreadsheet.

To try another model, including other providers that [LiteLLM](https://docs.litellm.ai) supports, add its key to `.env` and run `make run MODEL=...` and `make consistency MODEL=...`. To include it in the check for remembered answers, add its training cutoff to `TRAINING_CUTOFFS` in `src/petition_router/results.py`.

Everything is saved in `data/` and `results/`. Commit both, so anyone can check the numbers. If you clone this repository, the labels in `results/my-labels.json` are mine. Move that file aside to label your own.

## Known problems

- The tagged department is not always the only reasonable answer. Some petitions touch two or three departments, and the government picks one to respond.
- Models may have seen these petitions, and their responses, during training. The results compare the petitions answered before and after each model's training cutoff, but only 71 were answered after it, so only a big effect would show.
- One person labelled 100 petitions. Differences of less than about 10 points between me and a model are hard to tell from noise.
- The models get only the department names, with no examples. A prompt with examples might do better.
- Models run at their default settings, because Claude's 5.5 models only accept the default temperature. So some answers change from run to run, which is what asking again measures.
- Only the current Parliament's petitions are used, because older ones are tagged with departments that have since been merged or renamed.

## Development

`make test` runs the Python and TypeScript tests. `make lint` runs ruff, the TypeScript compiler and Prettier. To work on the pages with live reloading, run `uv run petition-router serve` and `npm --prefix web run dev`, then open http://localhost:5173.

## Licence

The code is MIT licensed. Petition data contains Parliamentary information licensed under the [Open Parliament Licence v3.0](https://www.parliament.uk/site-information/copyright-parliament/open-parliament-licence/).

This is a personal project, not affiliated with UK Parliament or the UK government. Built with help from Claude, an AI assistant.
