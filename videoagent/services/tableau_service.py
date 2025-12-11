"""Tableau service for downloading dashboard data and images."""

import os
from pathlib import Path

from dotenv import load_dotenv
import tableauserverclient as TSC

from ..config.settings import get_tableau_settings


class TableauService:
    """Service for downloading Tableau dashboard data and images.

    This is a thin wrapper around tableauserverclient that provides:
    - Authentication (PAT or username/password)
    - List workbooks and views
    - Download view as CSV or image
    - Download workbook as PDF

    All business logic (topic mapping, batch downloads) should be handled
    at the workflow layer.
    """

    def __init__(self, env_file: str = ".env"):
        """Initialize Tableau service with settings from environment."""
        load_dotenv(env_file)
        self.settings = get_tableau_settings()
        self.server = TSC.Server(self.settings.server_url, use_server_version=True)
        self._sign_in()

    def _sign_in(self):
        """Sign in using PAT or username/password based on env config."""
        auth_method = os.getenv("TABLEAU_AUTH_METHOD", "username_password")

        if auth_method == "pat":
            pat_name = os.getenv("TABLEAU_PAT_NAME")
            pat_value = os.getenv("TABLEAU_PAT_VALUE")
            auth = TSC.PersonalAccessTokenAuth(pat_name, pat_value, site_id=self.settings.site_id)
        else:
            username = os.getenv("TABLEAU_USERNAME")
            password = os.getenv("TABLEAU_PASSWORD")
            auth = TSC.TableauAuth(username, password, site_id=self.settings.site_id)

        self.server.auth.sign_in(auth)

    def sign_out(self):
        """Sign out from Tableau Server."""
        self.server.auth.sign_out()

    def list_workbooks(self) -> list:
        """List all workbooks in the site."""
        return list(TSC.Pager(self.server.workbooks))

    def list_views(self) -> list:
        """List all views in the site."""
        return list(TSC.Pager(self.server.views))

    def list_views_in_workbook(self, workbook_id: str) -> list[dict]:
        """List all views/sheets in a specific workbook.

        Args:
            workbook_id: The Tableau workbook ID

        Returns:
            List of view dicts with id, name, sheet_type, content_url
        """
        workbook = self.server.workbooks.get_by_id(workbook_id)
        self.server.workbooks.populate_views(workbook)
        return [
            {
                "id": v.id,
                "name": v.name,
                "sheet_type": v.sheet_type,
                "content_url": v.content_url,
            }
            for v in workbook.views
        ]

    def download_view_image(self, view_id: str, output_path: Path | str | None = None) -> bytes:
        """Download a view as an image.

        Args:
            view_id: The Tableau view ID
            output_path: Optional path to save the image

        Returns:
            Image bytes
        """
        view = self.server.views.get_by_id(view_id)
        self.server.views.populate_image(view)
        image_data = view.image

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(image_data)

        return image_data

    def download_view_csv(self, view_id: str, output_path: Path | str | None = None) -> str:
        """Download a view's data as CSV.

        Args:
            view_id: The Tableau view ID
            output_path: Optional path to save the CSV

        Returns:
            CSV content as string
        """
        view = self.server.views.get_by_id(view_id)
        self.server.views.populate_csv(view)
        csv_data = b"".join(view.csv)

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(csv_data)

        return csv_data.decode("utf-8")

    def download_workbook_pdf(self, workbook_id: str, output_path: Path | str | None = None) -> bytes:
        """Download a workbook as PDF.

        Args:
            workbook_id: The Tableau workbook ID
            output_path: Optional path to save the PDF

        Returns:
            PDF bytes
        """
        workbook = self.server.workbooks.get_by_id(workbook_id)
        self.server.workbooks.populate_pdf(workbook)
        pdf_data = workbook.pdf

        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(pdf_data)

        return pdf_data

    def get_workbook(self, workbook_id: str):
        """Get workbook by ID."""
        return self.server.workbooks.get_by_id(workbook_id)

    def get_view(self, view_id: str):
        """Get view by ID."""
        return self.server.views.get_by_id(view_id)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.sign_out()
