from __future__ import annotations

from pathlib import Path
from datetime import datetime
from uuid import uuid4

from django.conf import settings
from django.shortcuts import render
from django.views import generic
from django.views.generic.edit import FormMixin
from django.utils.text import get_valid_filename

from catalog.models import ToolList
from .forms import LDAUploadForm
from catalog.services.lda import run_lda_from_csv


def index(request):
    """Home page"""
    tool_list = ToolList.objects.all()
    context = {
        "num_tools": tool_list.count(),
        "tool_list": tool_list,
    }
    return render(request, "index.html", context=context)


class ToolListView(generic.ListView):
    model = ToolList
    context_object_name = "tool_list"
    template_name = "catalog/tool_list.html"


class ToolDetailView(FormMixin, generic.DetailView):
    """
    (변경됨)
    - 질문 텍스트 입력이 아니라 CSV 업로드 후 LDA 실행
    - 결과: answer 텍스트 + 생성된 파일 목록(그래프 png, 결과 csv 등)
    """
    model = ToolList
    context_object_name = "tool"
    template_name = "catalog/tool_detail.html"
    form_class = LDAUploadForm

    # URL kwarg가 pk / primary_key 둘 다 올 수 있게 유연하게 처리
    def get_object(self, queryset=None):
        pk = self.kwargs.get("pk") or self.kwargs.get("primary_key")
        if pk is None:
            return super().get_object(queryset=queryset)
        return ToolList.objects.get(pk=pk)

    def get_success_url(self):
        return self.request.path

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if "form" not in ctx:
            ctx["form"] = self.get_form()
        # 템플릿에서 미디어 링크 생성용
        ctx["MEDIA_URL"] = settings.MEDIA_URL

        # 결과 렌더링용 기본값
        ctx.setdefault("answer", None)
        ctx.setdefault("files", [])
        ctx.setdefault("images", [])
        ctx.setdefault("uploaded_filename", None)
        ctx.setdefault("job_rel_dir", None)
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()

        answer = None
        files = []
        images = []
        uploaded_filename = None
        job_rel_dir = None

        if form.is_valid():
            f = form.cleaned_data["csv_file"]
            extra = (form.cleaned_data.get("extra_instruction") or "").strip()

            # --- 업로드 기본 검증(가벼운 방어) ---
            uploaded_filename = f.name
            ext = (Path(f.name).suffix or "").lower()
            if ext != ".csv":
                answer = "[오류] CSV 파일(.csv)만 업로드할 수 있습니다."
                ctx = self.get_context_data(
                    form=form, answer=answer, files=files, images=images,
                    uploaded_filename=uploaded_filename, job_rel_dir=job_rel_dir
                )
                return self.render_to_response(ctx)

            # 너무 큰 파일 업로드 방지(원하면 조정)
            MAX_MB = 50
            if hasattr(f, "size") and f.size and f.size > MAX_MB * 1024 * 1024:
                answer = f"[오류] 파일이 너무 큽니다. {MAX_MB}MB 이하만 허용합니다."
                ctx = self.get_context_data(
                    form=form, answer=answer, files=files, images=images,
                    uploaded_filename=uploaded_filename, job_rel_dir=job_rel_dir
                )
                return self.render_to_response(ctx)

            # --- 작업 디렉터리 생성: media/lda_results/tool_<id>/<timestamp>_<rand>/ ---
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            rand = uuid4().hex[:8]
            job_rel_dir = f"lda_results/tool_{self.object.pk}/{ts}_{rand}"
            job_dir = Path(settings.MEDIA_ROOT) / job_rel_dir
            job_dir.mkdir(parents=True, exist_ok=True)

            # --- 업로드 파일 저장 ---
            safe_name = get_valid_filename(f.name)
            upload_path = job_dir / f"input_{safe_name}"
            with upload_path.open("wb") as out:
                for chunk in f.chunks():
                    out.write(chunk)

            # --- OpenAI LDA 실행 + 파일 다운로드/저장 ---
            try:
                res = run_lda_from_csv(upload_path, job_dir, extra_instruction=extra)
                answer = res.answer_text
                files = res.saved_relpaths or []
                images = [p for p in files if p.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]

                # 파일이 하나도 없으면 사용자에게 원인을 힌트로 제공
                if not files:
                    answer = (answer or "").strip() or "[안내] 결과 파일이 생성되지 않았습니다. 프롬프트/도구 실행 실패 가능성이 있어 서버 로그를 확인하세요."
            except Exception as e:
                answer = f"[오류] {e}"

        ctx = self.get_context_data(
            form=form,
            answer=answer,
            files=files,
            images=images,
            uploaded_filename=uploaded_filename,
            job_rel_dir=job_rel_dir,
        )
        return self.render_to_response(ctx)


# (기존 urls.py가 function-based view를 쓰는 경우를 대비한 호환용)
# path("tools/<int:primary_key>/", views.tool_detail_view, ...) 같은 라우팅이 있어도 동작합니다.
def tool_detail_view(request, primary_key):
    return ToolDetailView.as_view()(request, pk=primary_key)
