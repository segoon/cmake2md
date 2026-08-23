# The product

cmake2md is a documentation generator for cmake.
It parses cmake source files, extracts doxygen-like comments,
and uses jinja templates to generate final documentation.

# User base

A user is usually a C/C++ developer with basic cmake syntax knowledge.
He might not be an expert in cmake syntax.

It should be easy to make familiar with cmake2md for users who have already used doxygen-like documentation generators for other languages.
The core principles must not contradict existing implementations to avoid user confusion.
The syntax should be the same/similar where appropriate.
If the semantics is distinct, the syntax must differ to avoid user confusion.

# UX

All user-visible behaviour should not surprise the user.
cmake2md has to identify user errors and inform the user, e.g. validate for tag name typos.
User-visible error messages must be human-readable and should suggest a possible fix.
