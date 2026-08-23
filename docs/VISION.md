# The product

cmake2doc is a documentation generator for cmake.
It parses cmake source files, extracts doxygen-like comments,
and uses jinja templates to generate final documentation.

# User base

A user is usually a C/C++ developer with basic cmake syntax knowledge.
He might not be an expert in cmake syntax.
Threat the user as if he is a cmake newbie.

Do not assume the user is familiar with any documentation generation system.
It should be easy to make familiar with cmake2doc for users who have already used doxygen-like documentation generators for other languages.
The core principles must not contradict existing implementations to avoid user confusion.
The syntax should be the same/similar where appropriate.
If the semantics is distinct, the syntax must differ to avoid user confusion.

# UX

All user-visible behaviour should not surprise the user.
cmake2doc has to identify user errors and inform the user, e.g. validate for tag name typos.
User-visible error messages must be human-readable and should suggest a possible fix.

All public settings (e.g. cmdline, config, tags) must be documented in `README.md`.
