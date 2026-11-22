Parseh transcript-review skills

These skills are for the copy/paste review of a transcript in Parseh (add a
video -> speech to text -> "Use an external chatbot · copy & paste"):

  parseh-asr-correction  for the "Suspect words" method
  parseh-asr-audit       for the "Whole text" method
  parseh-asr-workspace   for the "Reasoning workspace" method

Add the skill of the method you use to your own chatbot or agent, through its
own settings (most take this ZIP as it is, or the folder with its SKILL.md).
Then, in Parseh, prepare the prompt, copy it into the chatbot, and paste the
chatbot's answer back into Parseh's answer box. The prompt carries the
evidence; the skill carries the instructions and the exact form of the answer
Parseh reads. Nothing is changed until you accept it in Parseh.

The workspace's ZIP of a review already holds its skill (SKILL.md) and its
helper (review.py, standard-library Python): the chatbot needs its own file
and code tools to use them.

Skills provide instructions. They do not train a model, improve its command of
the language, or make a correction right.
