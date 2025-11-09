from django.shortcuts import render

# Create your views here.
from catalog.models import ToolList, AnalysisModel

def index(request):
	"""View function for home page of site."""

	# Generate counts of some of the main objects
	tool_list = ToolList.objects.all()
	context = {
		'num_tools': tool_list.count(),
		'tool_list': tool_list,
	}

	# Render the HTML template index.html with the data in the context variable
	return render(request, 'index.html', context=context)

from django.views import generic

class ToolListView(generic.ListView):
	model = ToolList
	context_object_name = 'tool_list'
	template_name = 'catalog/tool_list.html'

from django.views.generic.edit import FormMixin
from .forms import AskForm
from .services.lda import get_answer
	
class ToolDetailView(FormMixin, generic.DetailView):
    model = ToolList
    context_object_name = "tool"
    template_name = "catalog/tool_detail.html"
    form_class = AskForm

    def get_success_url(self):
        # 같은 URL로 리다이렉트하고 싶을 때 사용(PRG 패턴). 지금은 즉시 렌더링하므로 미사용.
        return self.request.path

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "form" not in ctx:
            ctx["form"] = self.get_form()
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()  # DetailView 필수
        form = self.get_form()
        question, answer = None, None

        if form.is_valid():
            question = form.cleaned_data["question"]
            try:
                answer = get_answer(question)
            except Exception as e:
                answer = f"[오류] {e}"

        ctx = self.get_context_data(form=form, question=question, answer=answer)
        return self.render_to_response(ctx)


from django.shortcuts import get_object_or_404

def tool_detail_view(request, primary_key):
	tool = get_object_or_404(ToolList, pk=primary_key)
	return render(request, 'catalog/tool_detail.html', context={'tool': tool})