import pdfplumber


def extract_products_from_pdf(pdf_path: str):
    all_orders = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:

            words = page.extract_words()

            # ===== TÌM ORDER ID =====
            order_positions = []
            for i, w in enumerate(words):
                if w["text"] == "Order" and i + 2 < len(words):
                    if words[i + 1]["text"] == "ID:":
                        order_id = words[i + 2]["text"]
                        order_positions.append((order_id, w["top"]))

            # ===== XỬ LÝ TỪNG ORDER =====
            for idx, (order_id, order_top) in enumerate(order_positions):

                if idx + 1 < len(order_positions):
                    next_order_top = order_positions[idx + 1][1]
                else:
                    next_order_top = float("inf")

                # ===== TÌM VÙNG PRODUCT =====
                start_top = None
                end_top = None

                for w in words:
                    if (
                        w["text"] == "Product"
                        and order_top < w["top"] < next_order_top
                    ):
                        start_top = w["top"]

                    if (
                        w["text"] == "Qty"
                        and start_top is not None
                        and order_top < w["top"] < next_order_top
                    ):
                        end_top = w["top"]

                    # if w["text"] == "SKU":
                    #     print(f"SKU x0: {w['x0']} - top: {w['top']}")
                    # if w["text"] == "Seller":
                    #     print(f"Seller SKU x0: {w['x0']} - top: {w['top']}")

                if start_top is None or end_top is None:
                    continue

                # ===== LỌC WORD TRONG BLOCK =====
                block_words = [
                    w for w in words
                    if start_top < w["top"] < end_top
                ]

                # ===== PHÂN THEO TỌA ĐỘ X =====
                product_name_words = []
                sku_words = []
                seller_sku_words = []
                qty_words = []

                for w in block_words:
                    x = w["x0"]

                    if 0 <= x < 129:
                        product_name_words.append(w["text"])
                    elif 129 <= x < 169:
                        sku_words.append(w["text"])
                    elif 169 <= x < 260:
                        seller_sku_words.append(w["text"])
                    elif x >= 260:
                        qty_words.append(w["text"])

                # ===== GỘP TEXT =====
                product_name = " ".join(product_name_words).strip()
                sku = " ".join(sku_words).strip()
                seller_sku = " ".join(seller_sku_words).strip()
                quantity = " ".join(qty_words).strip()

                all_orders.append({
                    "order_id": order_id,
                    "product_name": product_name,
                    "sku": sku,
                    "seller_sku": seller_sku,
                    "quantity": quantity
                })

    return all_orders


def main():
    pdf_path = "test-files/02-28_23-09-21_Shipping label+Packing slip.pdf"

    orders = extract_products_from_pdf(pdf_path)

    print("===== KẾT QUẢ =====")
    for order in orders:
        print("=" * 50)
        print("Order ID:", order["order_id"])
        print("Product Name:", order["product_name"])
        print("SKU:", order["sku"])
        print("Seller SKU:", order["seller_sku"])
        print("Qty:", order["quantity"])


if __name__ == "__main__":
    main()