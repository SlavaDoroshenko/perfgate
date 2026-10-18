import $ from "vendor:jquery";

import "./style.css";

// Classic jQuery page code: build a table row by row, set classes, data and handlers.
// jQuery 4.0 removes deprecated APIs and old-IE code; no runtime speed-up is claimed.
const $table = $("<table>").append("<tr><th>ID</th><th>Name</th><th>State</th></tr>");
for (let i = 0; i < 1500; i++) {
  const $row = $("<tr>")
    .append($("<td>").text(String(i)))
    .append($("<td>").text(`Row ${i}`))
    .append($("<td>").text(i % 3 === 0 ? "done" : "open"))
    .data("id", i)
    .toggleClass("odd", i % 2 === 1)
    .on("click", function (this: HTMLElement) {
      $(this).toggleClass("selected");
    });
  $table.append($row);
}
$("#out").append($table);
$table.find("tr.odd td:first-child").css("font-weight", "600");
