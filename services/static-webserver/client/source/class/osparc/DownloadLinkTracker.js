/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.DownloadLinkTracker", {
  extend: qx.core.Object,
  type: "singleton",

  properties: {
    downloading: {
      check: "Boolean",
      init: false,
      nullable: true
    }
  },

  members: {
    downloadLinkUnattended: function(url, fileName) {
      const downloadAnchorNode = document.createElement("a");
      downloadAnchorNode.setAttribute("href", url);
      downloadAnchorNode.setAttribute("download", fileName);
      downloadAnchorNode.setAttribute("osparc", "downloadFile");
      document.body.appendChild(downloadAnchorNode);
      this.setDownloading(true);
      downloadAnchorNode.click();
      document.body.removeChild(downloadAnchorNode);
      // This is needed to make it work in Firefox
      setTimeout(() => this.setDownloading(false), 100);
    }
  }
});
