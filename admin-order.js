var printButton = document.getElementById("printOrderDetail");

if (printButton) {
  printButton.addEventListener("click", function() {
    window.print();
  });
}
