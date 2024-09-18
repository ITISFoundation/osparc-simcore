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

  members: {
    // overridden
    updateDataRowElement : function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      const messageCellPos = 2;
      // extend collapse row
      const style = rowElem.style;
      if (rowInfo.selected) {
        let messageDiv = rowElem.children.item(messageCellPos)
        if (rowElem.children.item(messageCellPos).children.length) {
          messageDiv = rowElem.children.item(messageCellPos).children.item(0);
        }
        const extendedHeight = messageDiv.getBoundingClientRect().height + "px";
        style.height = extendedHeight;
        Array.from(rowElem.children).forEach(child => child.style.height = extendedHeight);
      } else {
        style.height = "19px";
      }
    }
  }
});
