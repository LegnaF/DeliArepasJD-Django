
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def enviar_correo_deli(
    destinatario,
    titulo,
    mensaje,
    nombre="",
    detalle="",
    boton_url="",
    boton_texto="",
    nota=""
):
    contexto = {
        "titulo": titulo,
        "mensaje": mensaje,
        "nombre": nombre,
        "detalle": detalle,
        "boton_url": boton_url,
        "boton_texto": boton_texto,
        "nota": nota,
    }

    html = render_to_string(
        "email/notificacion.html",
        contexto
    )

    texto = render_to_string(
        "email/notificacion.txt",
        contexto
    )

    correo = EmailMultiAlternatives(
        subject=titulo,
        body=texto,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[destinatario],
    )

    correo.attach_alternative(html, "text/html")

    return correo.send(fail_silently=False)
