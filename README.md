# Artemis Cosmos Mission Template

Use this as a template to create any Cosmos mission using the MAST language.

Learn how to use the [MAST Language](https://artemis-sbs.github.io/sbs_utils/).

## Creating a mission

From your `data/missions` folder:

```
sbs create MyMission
```

That picks a template, downloads it, and fetches the libraries it depends on. To see what
is on offer first:

```
sbs templates
```

You can still use the green **Use this template** button on GitHub instead - it gives you
the minimal mission at the repository root.

## Release lines

Each supported release line has its own branch, and a mission's dependencies are pinned to
one line. This is not just a version string: a template can only use language features that
exist on its line - `provides` / `requires`, for instance, are v1.4.0 and later - so the
branch decides which templates exist at all.

`sbs create` defaults to the highest line your install already has libraries for, capped by
your Cosmos version. It never picks a newer line just because GitHub has one; a mission your
engine cannot launch is not a useful starting point. Override with `-b` or `-l`.

## Adding a template

Templates live in `templates/<id>/`, each one self-contained - a whole mission folder you
can browse here on GitHub. The minimal mission stays at the repository root so the **Use
this template** button keeps working.

Add a folder, then an entry in `templates.json`:

```json
{
    "id": "amd",
    "title": "AMD-driven mission",
    "blurb": "Dialogue and quests declared in .amd files.",
    "path": "templates/amd",
    "tags": ["mast", "amd"]
}
```

`sbs create` and `sbs templates` read that file from the branch, so a new template needs no
new release of the `sbs` tool. CI creates and compiles every entry on every push - a
template that does not compile does not merge.
