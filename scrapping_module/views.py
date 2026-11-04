from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .services import GerarComprasError, gerar_compras, xml_to_json, decrease_counter


@require_GET
def compra(request):
    try:
        xml = gerar_compras()
    except GerarComprasError as exc:
        return JsonResponse(
            {"erro": "Falha ao chamar o serviço gerar-compras", "detalhe": str(exc)},
            status=502,
        )

    decrease_counter()

    response = xml_to_json(xml)

    return HttpResponse(response, content_type="application/json; charset=utf-8")