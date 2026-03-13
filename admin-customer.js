var printButton = document.getElementById("printCustomerHistory");

if (printButton) {
  printButton.addEventListener("click", function() {
    window.print();
  });
}
