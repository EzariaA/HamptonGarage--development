# backend/tests/test_email_domain_rule.py
# Created by Kyle Lewis 11/11/26 - Iteration 4
# Unit tests for the email domain rule function only (AuthService.is_student_email).
# The signup and login routes are tested separately by Clarence.
# Test IDs ED-1 to ED-6

from services.auth_services import AuthService

service = AuthService()


# ED-1: student domain is allowed
def test_student_domain_is_allowed():
    assert service.is_student_email("jsmith@my.hamptonu.edu") == True


# ED-2: faculty/staff domain is allowed
def test_hamptonu_domain_is_allowed():
    assert service.is_student_email("jsmith@hamptonu.edu") == True


# ED-3: capital letters in the domain still count
def test_domain_check_ignores_capital_letters():
    assert service.is_student_email("jsmith@My.HamptonU.edu") == True
    assert service.is_student_email("jsmith@HAMPTONU.EDU") == True


# ED-4: fake look-alike domains are rejected
def test_fake_domains_are_rejected():
    assert service.is_student_email("jsmith@fakehamptonu.edu") == False
    assert service.is_student_email("jsmith@notmy.hamptonu.edu") == False
    assert service.is_student_email("jsmith@hamptonu.edu.com") == False
    assert service.is_student_email("jsmith@hamptonu.edu.evil.com") == False


# ED-5: other email providers are rejected
def test_other_domains_are_rejected():
    assert service.is_student_email("jsmith@gmail.com") == False
    assert service.is_student_email("jsmith@hampton.edu") == False


# ED-6: badly formed emails are rejected
def test_badly_formed_emails_are_rejected():
    assert service.is_student_email("") == False
    assert service.is_student_email(None) == False
    assert service.is_student_email("@hamptonu.edu") == False
    assert service.is_student_email("jsmith.hamptonu.edu") == False
    assert service.is_student_email("j@smith@hamptonu.edu") == False
