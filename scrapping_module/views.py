from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .services import GerarComprasError, gerar_compras


@require_GET
def compra(request):
    try:
        xml = gerar_compras()
    except GerarComprasError as exc:
        return JsonResponse(
            {"erro": "Falha ao chamar o serviço gerar-compras", "detalhe": str(exc)},
            status=502,
        )

    return HttpResponse(xml, content_type="application/xml; charset=utf-8")