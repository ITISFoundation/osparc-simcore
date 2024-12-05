/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.table.rowrenderer.ExpandSelection", {
  extend: qx.ui.table.rowrenderer.Default,

  construct: function(_, expandableColPos = 2) {
    this.base(arguments);

    this.__expandableColPos = expandableColPos;
  },

  members: {
    __expandableColPos: null,

    // overridden
    updateDataRowElement : function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      const messageCellPos = this.__expandableColPos;
      // extend collapse row
      const style = rowElem.style;
      if (rowInfo.selected) {
        const messageDiv = rowElem.children.item(messageCellPos);
        const expandedHeight = messageDiv.scrollHeight + "px";
        style.height = expandedHeight;
        Array.from(rowElem.children).forEach(child => child.style.height = expandedHeight);
      } else {
        // back to collapsed
        style.height = "19px";
      }
    }
  }
});
