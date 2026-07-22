from django.urls import path

from .views import EditorTransformView
from .wizard_views import WizardGenerateView, WizardQuestionsView, WizardReviewView

urlpatterns = [
    path("editor/transform/", EditorTransformView.as_view(), name="ai-editor-transform"),
    path("wizard/questions/", WizardQuestionsView.as_view(), name="ai-wizard-questions"),
    path("wizard/review/", WizardReviewView.as_view(), name="ai-wizard-review"),
    path("wizard/generate/", WizardGenerateView.as_view(), name="ai-wizard-generate"),
]
