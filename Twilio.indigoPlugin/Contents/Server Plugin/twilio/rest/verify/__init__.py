# coding=utf-8
r"""
This code was generated by
\ / _    _  _|   _  _
 | (_)\/(_)(_|\/| |(/_  v1.0.0
      /       /
"""

from twilio.base.domain import Domain
from twilio.rest.verify.v2 import V2


class Verify(Domain):

    def __init__(self, twilio):
        """
        Initialize the Verify Domain

        :returns: Domain for Verify
        :rtype: twilio.rest.verify.Verify
        """
        super(Verify, self).__init__(twilio)

        self.base_url = 'https://verify.twilio.com'

        # Versions
        self._v2 = None

    @property
    def v2(self):
        """
        :returns: Version v2 of verify
        :rtype: twilio.rest.verify.v2.V2
        """
        if self._v2 is None:
            self._v2 = V2(self)
        return self._v2

    @property
    def forms(self):
        """
        :rtype: twilio.rest.verify.v2.form.FormList
        """
        return self.v2.forms

    @property
    def services(self):
        """
        :rtype: twilio.rest.verify.v2.service.ServiceList
        """
        return self.v2.services

    @property
    def verification_attempts(self):
        """
        :rtype: twilio.rest.verify.v2.verification_attempt.VerificationAttemptList
        """
        return self.v2.verification_attempts

    def __repr__(self):
        """
        Provide a friendly representation

        :returns: Machine friendly representation
        :rtype: str
        """
        return '<Twilio.Verify>'
