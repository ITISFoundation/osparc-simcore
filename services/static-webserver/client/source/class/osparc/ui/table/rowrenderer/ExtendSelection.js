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

qx.Class.define("osparc.ui.table.rowrenderer.ExtendSelection", {
  extend: qx.ui.table.rowrenderer.Default,

  members: {
    // overridden
    updateDataRowElement : function(rowInfo, rowElem) {
      this.base(arguments, rowInfo, rowElem);

      // extend collapse row
      const style = rowElem.style;
      if (rowInfo.selected) {
        const messageDiv = rowElem.children.item(2).children.item(0);
        const extendedHeight = messageDiv.getBoundingClientRect().height + "px";
        style.height = extendedHeight;
        Array.from(rowElem.children).forEach(child => child.style.height = extendedHeight);
      } else {
        style.height = "19px";
      }
    }
  }
});
