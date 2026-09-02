import os
import glob
import io
from subprocess import check_output, CalledProcessError, STDOUT, TimeoutExpired

from src.PreambleManager import PreambleManager
from src.LoggingServer import LoggingServer


class LatexConverter():

    logger = LoggingServer.getInstance()

    SAFE_ENV = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "openin_any": "p",
        "openout_any": "p",
    }

    def __init__(self, preambleManager, userOptionsManager):
        self._preambleManager = preambleManager
        self._userOptionsManager = userOptionsManager

    def extractBoundingBox(self, dpi, pathToPdf):
        try:
            bbox = check_output([
                "gs", "-dSAFER", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=bbox", pathToPdf
            ], stderr=STDOUT, env=self.SAFE_ENV).decode("ascii")
        except CalledProcessError:
            raise ValueError("Could not extract bounding box! Empty expression?")

        try:
            bounds = [int(_) for _ in bbox[bbox.index(":")+2:bbox.index("\n")].split(" ")]
        except ValueError:
            raise ValueError("Could not parse bounding box! Empty expression?")

        if bounds[0] == bounds[2] or bounds[1] == bounds[3]:
            self.logger.warn("Expression had zero width/height bbox!")
            raise ValueError("Empty expression!")

        hpad = 0.25 * 72.27  # 72 postscript points = 1 inch
        vpad = .1 * 72.27
        llc = bounds[:2]
        llc[0] -= hpad
        llc[1] -= vpad
        ruc = bounds[2:]
        ruc[0] += hpad
        ruc[1] += vpad
        size_factor = dpi / 72.27
        width = (ruc[0] - llc[0]) * size_factor
        height = (ruc[1] - llc[1]) * size_factor
        translation_x = llc[0]
        translation_y = llc[1]
        return width, height, -translation_x, -translation_y

    def correctBoundingBoxAspectRaito(self, dpi, boundingBox, maxWidthToHeight=3, maxHeightToWidth=1):
        width, height, translation_x, translation_y = boundingBox
        size_factor = dpi / 72.27
        if width > maxWidthToHeight * height:
            translation_y += (width / maxWidthToHeight - height) / 2 / size_factor
            height = width / maxWidthToHeight
        elif height > maxHeightToWidth * width:
            translation_x += (height / maxHeightToWidth - width) / 2 / size_factor
            width = height / maxHeightToWidth
        return width, height, translation_x, translation_y

    def getError(self, log):
        for idx, line in enumerate(log):
            if line[:2] == "! ":
                return "".join(log[idx:idx+2])
        return "Unknown LaTeX compilation error"

    def pdflatex(self, fileName, userId=None):
        cmd = ['xelatex']

        # 白名單判定
        if userId in [691216126]:
            cmd.append('-shell-escape')
        else:
            cmd.append('-no-shell-escape')

        cmd.extend([
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-output-directory", "build",
            fileName
        ])

        try:
            check_output(
                cmd,
                stderr=STDOUT,
                timeout=16,
                env=self.SAFE_ENV
            )
        except CalledProcessError:
            log_file = os.path.splitext(fileName)[0] + ".log"
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    msg = self.getError(f.readlines())
            except Exception:
                msg = "LaTeX compilation failed and log could not be read."
            self.logger.debug(msg)
            raise ValueError(msg)
        except TimeoutExpired:
            msg = "xelatex has likely hung up and had to be killed. Congratulations!"
            raise ValueError(msg)

    def cropPdf(self, sessionId):
        pdf_file = f"build/expression_file_{sessionId}.pdf"
        bbox = check_output([
            "gs", "-dSAFER", "-q", "-dBATCH", "-dNOPAUSE", "-sDEVICE=bbox", pdf_file
        ], stderr=STDOUT, env=self.SAFE_ENV).decode("ascii")

        bounds = tuple([int(_) for _ in bbox[bbox.index(":")+2:bbox.index("\n")].split(" ")])

        cmd = [
            "gs", "-dSAFER",
            "-o", f"build/expression_file_cropped_{sessionId}.pdf",
            "-sDEVICE=pdfwrite",
            "-c", f"[/CropBox [{bounds[0]} {bounds[1]} {bounds[2]} {bounds[3]}] /PAGES pdfmark",
            "-f", pdf_file
        ]
        check_output(cmd, stderr=STDOUT, env=self.SAFE_ENV)

    def convertPdfToPng(self, dpi, sessionId, bbox):
        cmd = [
            "gs", "-dSAFER",
            "-o", f"build/expression_{sessionId}.png",
            f"-r{int(dpi)}",
            "-sDEVICE=pngalpha",
            f"-g{int(bbox[0])}x{int(bbox[1])}",
            "-dLastPage=1",
            "-c", f"<</Install {{{int(bbox[2])} {int(bbox[3])} translate}}>> setpagedevice",
            "-f", f"build/expression_file_{sessionId}.pdf"
        ]
        check_output(cmd, stderr=STDOUT, env=self.SAFE_ENV)

    def convertExpression(self, expression, userId, sessionId, returnPdf=False):
        if r"\documentclass" in expression:
            fileString = expression
        else:
            try:
                preamble = self._preambleManager.getPreambleFromDatabase(userId)
                self.logger.debug("Preamble for userId %d found", userId)
            except KeyError:
                self.logger.debug("Preamble for userId %d not found, using default preamble", userId)
                preamble = self._preambleManager.getDefaultPreamble()
            finally:
                fileString = preamble + "\n\\begin{document}\n" + expression + "\n\\end{document}"

        tex_path = f"build/expression_file_{sessionId}.tex"
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(fileString)

        dpi = self._userOptionsManager.getDpiOption(userId)

        try:
            self.pdflatex(tex_path, userId)

            pdf_path = f"build/expression_file_{sessionId}.pdf"
            bbox = self.extractBoundingBox(dpi, pdf_path)
            bbox = self.correctBoundingBoxAspectRaito(dpi, bbox)
            self.convertPdfToPng(dpi, sessionId, bbox)

            self.logger.debug("Generated image for %s", expression)

            png_path = f"build/expression_{sessionId}.png"
            with open(png_path, "rb") as f:
                imageBinaryStream = io.BytesIO(f.read())

            if returnPdf:
                self.cropPdf(sessionId)
                cropped_pdf_path = f"build/expression_file_cropped_{sessionId}.pdf"
                with open(cropped_pdf_path, "rb") as f:
                    pdfBinaryStream = io.BytesIO(f.read())
                return imageBinaryStream, pdfBinaryStream
            else:
                return imageBinaryStream

        finally:
            for temp_file in glob.glob(f"build/*_{sessionId}.*"):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
