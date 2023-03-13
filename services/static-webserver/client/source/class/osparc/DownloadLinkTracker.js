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
      this.setDownloading(true);
      downloadAnchorNode.click();
      this.setDownloading(false);
      downloadAnchorNode.remove();
    }
  }
});
