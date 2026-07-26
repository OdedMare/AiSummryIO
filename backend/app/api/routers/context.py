"""The dependency bundle every router is built from.

Routers are constructed by ``main.py`` and handed this object, so no router
imports the composition root. That keeps the import graph one-way and lets a
test build a router over fakes without a database.
"""


class ApiContext:
    def __init__(
        self, repository, service, jobs, store, llm,
        admin_dependency, user_session, set_session_cookie,
    ):
        self.repository = repository
        self.service = service
        self.jobs = jobs
        self.store = store
        self.llm = llm
        self.admin_dependency = admin_dependency
        self.user_session = user_session
        self.set_session_cookie = set_session_cookie
