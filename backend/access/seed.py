"""Two demo banks. Both are Synthetic: no real institution or person is represented."""

from access.directory import AccessDirectory
from access.models import Employee, Institution, Office


def demo_directory() -> AccessDirectory:
    institutions = [
        Institution("A", "Demo Public Bank (Synthetic)", "PUBLIC"),
        Institution("B", "Demo Private Bank (Synthetic)", "PRIVATE"),
    ]
    offices = [
        Office("A-HO", "A", None, "HEAD"),
        Office("A-RG1", "A", "A-HO", "REGION"),
        Office("A-BR1", "A", "A-RG1", "BRANCH"),
        Office("A-BR2", "A", "A-RG1", "BRANCH"),
        Office("B-HO", "B", None, "HEAD"),
        Office("B-BR1", "B", "B-HO", "BRANCH"),
    ]
    employees = [
        Employee("investigator", "A", "A-BR1", "INVESTIGATOR"),
        Employee("investigator_a1b", "A", "A-BR1", "INVESTIGATOR"),
        Employee("analyst_a2", "A", "A-BR2", "INVESTIGATOR"),
        Employee("supervisor", "A", "A-HO", "SUPERVISOR"),
        Employee("investigator_b", "B", "B-BR1", "INVESTIGATOR"),
        Employee("supervisor_b", "B", "B-HO", "SUPERVISOR"),
    ]
    return AccessDirectory(institutions, offices, employees)
