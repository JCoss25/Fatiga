"""Envio de correo: SMTP configurable + modo simulado.

Si no hay SMTP_HOST (o CORREO_SIMULADO=1), el correo no sale: se imprime en
consola y se guarda en la tabla `cot_correos` para verlo en la bandeja interna
del aprobador. Asi se puede probar todo el flujo en local.
"""
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]  # app-fatiga/
load_dotenv(ROOT / ".env")

SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER).strip()
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Kogn1v1s - Comercial")
SMTP_TLS = os.getenv("SMTP_TLS", "starttls").strip().lower()  # starttls | ssl | none
BASE_URL = os.getenv("APP_URL", "http://127.0.0.1:8010").rstrip("/")
APP_URL = BASE_URL + "/comercial"
SIMULADO = os.getenv("CORREO_SIMULADO", "0").strip() == "1"


def configurado() -> bool:
    return bool(SMTP_HOST and SMTP_FROM and not SIMULADO)


def enviar(destinatario: str, asunto: str, texto: str, html: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Devuelve (estado, error). estado: SIMULADO | ENVIADO | ERROR."""
    if not destinatario:
        return "ERROR", "La solicitud no tiene correo de destinatario."
    if not configurado():
        print("\n" + "=" * 72)
        print("[CORREO SIMULADO] Para:", destinatario)
        print("Asunto:", asunto)
        print("-" * 72)
        print(texto)
        print("=" * 72 + "\n")
        return "SIMULADO", None

    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM))
    msg["To"] = destinatario
    msg.set_content(texto)
    if html:
        msg.add_alternative(html, subtype="html")

    try:
        if SMTP_TLS == "ssl":
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                if SMTP_USER:
                    smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
                smtp.ehlo()
                if SMTP_TLS == "starttls":
                    smtp.starttls()
                    smtp.ehlo()
                if SMTP_USER:
                    smtp.login(SMTP_USER, SMTP_PASSWORD)
                smtp.send_message(msg)
        return "ENVIADO", None
    except smtplib.SMTPAuthenticationError:
        return "ERROR", (
            "Gmail rechazó el usuario/contraseña. Usa una contraseña de aplicación "
            "de 16 caracteres (no la contraseña normal de la cuenta)."
        )
    except smtplib.SMTPServerDisconnected:
        return "ERROR", (
            "Gmail cerró la conexión. Verifica que SMTP_PASSWORD sea una contraseña "
            "de aplicación (16 caracteres) y que la cuenta tenga verificación en 2 pasos."
        )
    except Exception as e:  # noqa: BLE001
        return "ERROR", str(e)[:500]


def _money(valor, moneda: str = "MXN") -> str:
    try:
        n = float(valor or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"${n:,.2f} {moneda or 'MXN'}"


def _html(titulo: str, cuerpo: str, boton_texto: str, boton_url: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="es"><body style="margin:0;padding:0;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#1e293b;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f1f5f9;padding:28px 12px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:620px;background:#ffffff;border:1px solid #e2e8f0;border-radius:16px;overflow:hidden;">
        <tr><td style="background:#4338ca;padding:20px 28px;color:#ffffff;">
          <div style="font-size:13px;letter-spacing:.08em;text-transform:uppercase;opacity:.85;">Kogn1v1s · Cotización de daños</div>
          <div style="font-size:22px;font-weight:bold;margin-top:4px;">{titulo}</div>
        </td></tr>
        <tr><td style="padding:26px 28px;font-size:15px;line-height:1.6;">{cuerpo}</td></tr>
        <tr><td style="padding:0 28px 30px;">
          <a href="{boton_url}" style="display:inline-block;background:#4338ca;color:#ffffff;text-decoration:none;padding:12px 22px;border-radius:10px;font-weight:bold;font-size:14px;">{boton_texto}</a>
          <p style="margin:18px 0 0;font-size:12px;color:#94a3b8;word-break:break-all;">{boton_url}</p>
        </td></tr>
      </table>
      <p style="font-size:11px;color:#94a3b8;margin-top:16px;">Correo automático del módulo de Cotización de daños. No responder a este mensaje.</p>
    </td></tr>
  </table>
</body></html>"""


def correo_solicitud(sol) -> Tuple[str, str, str]:
    asunto = f"Nueva solicitud {sol.folio} · {sol.descripcion[:60]}"
    texto = (
        f"Se registró una nueva solicitud de cotización de daños.\n\n"
        f"Folio: {sol.folio}\n"
        f"Solicitante / Cliente: {sol.solicitante_cliente}\n"
        f"VIN: {sol.vin or '—'}\n"
        f"Ubicación: {sol.ubicacion or '—'}\n"
        f"Tipo de servicio: {sol.tipo_servicio or '—'}\n"
        f"No. de parte: {sol.no_parte or '—'}\n"
        f"Descripción: {sol.descripcion}\n"
        f"Cantidad: {sol.cantidad}\n"
        f"Precio: {_money(sol.total, sol.moneda)}\n"
        f"Fecha requerida / ETA: {sol.fecha_requerida or '—'}\n\n"
        f"Revisa y aprueba o comenta la solicitud en:\n"
        f"{APP_URL}/aprobador.html?id={sol.id_solicitud}\n"
    )
    cuerpo = f"""
      <p style="margin:0 0 14px;">Se registró una nueva <strong>solicitud de cotización de daños</strong> que requiere tu revisión.</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:6px 0;color:#64748b;">Folio</td><td style="padding:6px 0;font-weight:bold;">{sol.folio}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Solicitante / Cliente</td><td style="padding:6px 0;">{sol.solicitante_cliente}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">VIN</td><td style="padding:6px 0;">{sol.vin or '—'}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Descripción</td><td style="padding:6px 0;">{sol.descripcion}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Total</td><td style="padding:6px 0;font-weight:bold;">{_money(sol.total, sol.moneda)}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">ETA</td><td style="padding:6px 0;">{sol.fecha_requerida or '—'}</td></tr>
      </table>
      <p style="margin:16px 0 0;color:#b45309;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:10px 12px;font-size:13px;">
        Si no se aprueba en 2 días se enviará un recordatorio automático.
      </p>
    """
    return asunto, texto, _html("Nueva solicitud pendiente", cuerpo, "Revisar solicitud", f"{APP_URL}/aprobador.html?id={sol.id_solicitud}")


def correo_recordatorio(sol, dias: int) -> Tuple[str, str, str]:
    asunto = f"Recordatorio: la solicitud {sol.folio} sigue pendiente de aprobación"
    texto = (
        f"La solicitud {sol.folio} lleva {dias} días sin aprobación.\n\n"
        f"Solicitante / Cliente: {sol.solicitante_cliente}\n"
        f"Descripción: {sol.descripcion}\n"
        f"Total: {_money(sol.total, sol.moneda)}\n\n"
        f"Revisa la solicitud en:\n{APP_URL}/aprobador.html?id={sol.id_solicitud}\n"
    )
    cuerpo = f"""
      <p style="margin:0 0 14px;">La siguiente solicitud <strong>lleva {dias} días pendiente</strong> de aprobación:</p>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <tr><td style="padding:6px 0;color:#64748b;">Folio</td><td style="padding:6px 0;font-weight:bold;">{sol.folio}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Solicitante / Cliente</td><td style="padding:6px 0;">{sol.solicitante_cliente}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Descripción</td><td style="padding:6px 0;">{sol.descripcion}</td></tr>
        <tr><td style="padding:6px 0;color:#64748b;">Total</td><td style="padding:6px 0;font-weight:bold;">{_money(sol.total, sol.moneda)}</td></tr>
      </table>
      <p style="margin:16px 0 0;color:#b91c1c;background:#fef2f2;border:1px solid #fecaca;border-radius:10px;padding:10px 12px;font-size:13px;">
        Se enviará un recordatorio cada 2 días hasta que la solicitud sea aprobada o rechazada.
      </p>
    """
    return asunto, texto, _html("Recordatorio de aprobación", cuerpo, "Atender solicitud", f"{APP_URL}/aprobador.html?id={sol.id_solicitud}")


def correo_decision(sol, aprobada: bool, comentario: Optional[str]) -> Tuple[str, str, str]:
    estado = "APROBADA" if aprobada else "RECHAZADA"
    asunto = f"Tu solicitud {sol.folio} fue {estado.lower()}"
    sb = f"Número de SB: {sol.numero_sb}\n" if sol.numero_sb else ""
    enlace_solicitud = f"{APP_URL}/solicitante.html?id={sol.id_solicitud}"
    seguimiento = (
        "Cuando se realice la compra, marca la solicitud como COMPRADA y al terminar como CERRADA:\n"
        f"{enlace_solicitud}\n\n"
        if aprobada else
        "Puedes corregir y reenviar la solicitud en:\n"
        f"{enlace_solicitud}\n\n"
    )
    texto = (
        f"La solicitud {sol.folio} fue {estado}.\n\n"
        f"{sb}"
        f"Comentario del aprobador: {comentario or '—'}\n\n"
        f"{seguimiento}"
        f"Consulta el documento en:\n{APP_URL}/documento.html?id={sol.id_solicitud}\n"
    )
    color = "#047857" if aprobada else "#b91c1c"
    fondo = "#ecfdf5" if aprobada else "#fef2f2"
    seguimiento_html = (
        f'<p style="margin:14px 0 0;font-size:13px;color:#334155;">Cuando se realice la compra, entra a '
        f'<a href="{enlace_solicitud}">tu solicitud</a> y marca <strong>COMPRADO</strong>; '
        f'al terminar, <strong>CERRADO</strong>.</p>'
        if aprobada else
        f'<p style="margin:14px 0 0;font-size:13px;color:#334155;">Puedes corregir y reenviar la solicitud en '
        f'<a href="{enlace_solicitud}">el portal</a>.</p>'
    )
    cuerpo = f"""
      <p style="margin:0 0 14px;">La solicitud <strong>{sol.folio}</strong> fue
        <strong style="color:{color};">{estado}</strong>.</p>
      <div style="background:{fondo};border:1px solid #e2e8f0;border-radius:10px;padding:12px 14px;font-size:14px;">
        {f'<div><strong>Número de SB:</strong> {sol.numero_sb}</div>' if sol.numero_sb else ''}
        <div style="margin-top:6px;"><strong>Comentario:</strong> {comentario or '—'}</div>
      </div>
      {seguimiento_html}
    """
    return asunto, texto, _html(f"Solicitud {estado.lower()}", cuerpo, "Ver documento", f"{APP_URL}/documento.html?id={sol.id_solicitud}")
