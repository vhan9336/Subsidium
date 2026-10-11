# Slides

The walkthrough opened with **E** in the app is built from this folder.

- Each slide is one HTML file. Slides play in alphabetical order, so name them `01-intro.html`, `02-problem.html` and so on. Use `10-` and up with two digits so the order stays right.
- A file whose name starts with `_` is skipped, and so is `README.md`. Use `_draft.html` to hide a slide.
- Every file starts from the same template and links `slide.css`, which draws the slide on a 1280 x 720 canvas. The app scales that canvas to fit the window.
- Put pictures in `images/` and reference them relatively:
  `<img class="shot" src="images/lander.png" alt="...">`.
  For text beside a picture, wrap both in `<div class="split">`.
- The list is read each time the walkthrough opens, so adding a file needs no rebuild.

Template:

```html
<!doctype html>
<meta charset="utf-8">
<link rel="stylesheet" href="slide.css">
<h1>Title</h1>
<p class="lead">One sentence that says the point.</p>
<ul><li>Supporting fact.</li></ul>
```
