ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY service.py /opt/aryn/operational_service.py
USER 65532:65532
ENTRYPOINT ["python", "-B", "/opt/aryn/operational_service.py"]
