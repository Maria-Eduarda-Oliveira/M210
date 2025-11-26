import streamlit as st
import pulp

st.title("Simplex Tableau")
tipo = st.selectbox("Tipo do problema", ["Maximizar", "Minimizar"])
n = st.selectbox("Número de variáveis :", [2, 3, 4])
st.subheader("Função Objetivo")
obj = [st.number_input(f"Coeficiente de x{i+1}", value=0.0) for i in range(n)]
m = st.number_input("Quantas restrições?", min_value=1,
                    max_value=10, value=2, step=1)

A, b, delta, signal = [], [], [], []

st.subheader("Restrições")
for j in range(m):
    st.write(f"Restrição {j+1}")
    A.append(
        [st.number_input(f"x{i+1} (R{j+1})", value=0.0) for i in range(n)])

    signal.append(
        st.selectbox(
            f"Tipo da restrição {j+1}",
            ["<=", ">=", "="],
            key=j
        )
    )

    b.append(st.number_input(f"LD{j+1}", value=0.0))

    delta.append(
        st.number_input(
            f"Variação desejada na restrição {j+1}",
            value=0.0
        )
    )

if st.button("Resolver"):
    x = [pulp.LpVariable(f"x{i+1}", lowBound=0) for i in range(n)]

    prob = pulp.LpProblem(
        "PPL",
        pulp.LpMinimize if tipo == "Minimizar" else pulp.LpMaximize
    )

    prob += sum(obj[i] * x[i] for i in range(n))

    for j in range(m):
        expr = sum(A[j][i] * x[i] for i in range(n))

        if signal[j] == "<=":
            prob += expr <= b[j]
        elif signal[j] == ">=":
            prob += expr >= b[j]
        else:
            prob += expr == b[j]

    prob.solve()

    st.subheader("Resultado")
    st.write({f"x{i+1}": v.value() for i, v in enumerate(x)})
    st.write("Valor da Função Objetivo:", pulp.value(prob.objective))

    st.subheader("Preços-Sombra (Dual)")
    try:
        y = [c.pi for c in prob.constraints.values()]
        st.write({f"Restrição {j+1}": y[j] for j in range(m)})
    except:
        st.write(
            "Dual não disponível (provavelmente devido a '≥' ou '=' em algumas restrições)."
        )

    new_b = [b[j] + delta[j] for j in range(m)]

    prob2 = pulp.LpProblem(
        "NovoPPL",
        pulp.LpMinimize if tipo == "Minimizar" else pulp.LpMaximize
    )

    x2 = [pulp.LpVariable(f"x{i+1}", lowBound=0) for i in range(n)]
    prob2 += sum(obj[i] * x2[i] for i in range(n))

    for j in range(m):
        expr = sum(A[j][i] * x2[i] for i in range(n))

        if signal[j] == "<=":
            prob2 += expr <= new_b[j]
        elif signal[j] == ">=":
            prob2 += expr >= new_b[j]
        else:
            prob2 += expr == new_b[j]

    prob2.solve()

    st.subheader("Análise com alterações")
    if pulp.LpStatus[prob2.status] != "Optimal":
        st.error("Alterações inviáveis.")
    else:
        st.success("Alterações viáveis.")
        st.write("Novo valor da função objetivo:", pulp.value(prob2.objective))

        # Calcular limites de validade dos preços-sombra através de análise de sensibilidade
        st.write("Limites válidos dos preços-sombra:")
        shadow_price_limits = {}

        for j in range(m):
            if y[j] is not None and y[j] != 0:
                original_b = b[j]
                # Calcular limites através de busca binária aproximada
                # Encontrar o maior aumento e diminuição onde o preço-sombra permanece válido

                def test_shadow_price(test_b_value):
                    """Testa se o preço-sombra permanece o mesmo para um valor de b[j]"""
                    test_prob = pulp.LpProblem(
                        "Test", pulp.LpMinimize if tipo == "Minimizar" else pulp.LpMaximize)
                    test_x = [pulp.LpVariable(
                        f"x{i+1}", lowBound=0) for i in range(n)]
                    test_prob += sum(obj[i] * test_x[i] for i in range(n))

                    for k in range(m):
                        test_expr = sum(A[k][i] * test_x[i] for i in range(n))
                        if k == j:
                            if signal[j] == "<=":
                                test_prob += test_expr <= test_b_value
                            elif signal[j] == ">=":
                                test_prob += test_expr >= test_b_value
                            else:
                                test_prob += test_expr == test_b_value
                        else:
                            if signal[k] == "<=":
                                test_prob += test_expr <= b[k]
                            elif signal[k] == ">=":
                                test_prob += test_expr >= b[k]
                            else:
                                test_prob += test_expr == b[k]

                    test_prob.solve()
                    if pulp.LpStatus[test_prob.status] == "Optimal":
                        test_y = list(test_prob.constraints.values())[j].pi
                        return test_y is not None and abs(test_y - y[j]) < 1e-6
                    return False

                # Buscar limite superior
                upper_limit = original_b
                step = max(abs(original_b) * 0.1,
                           1.0) if original_b != 0 else 1.0
                for _ in range(20):  # Limitar iterações
                    if test_shadow_price(upper_limit + step):
                        upper_limit += step
                        step *= 1.5
                    else:
                        break

                # Buscar limite inferior
                lower_limit = original_b
                step = max(abs(original_b) * 0.1,
                           1.0) if original_b != 0 else 1.0
                for _ in range(20):  # Limitar iterações
                    if test_shadow_price(lower_limit - step):
                        lower_limit -= step
                        step *= 1.5
                    else:
                        break

                shadow_price_limits[f"Restrição {j+1}"] = (
                    f"Preço-sombra: {y[j]:.4f}, "
                    f"Válido para b[{j+1}] entre {lower_limit:.4f} e {upper_limit:.4f}"
                )
            elif y[j] is not None:
                shadow_price_limits[
                    f"Restrição {j+1}"] = f"Preço-sombra: {y[j]:.4f} (restrição não ativa)"
            else:
                shadow_price_limits[f"Restrição {j+1}"] = "Preço-sombra não disponível"

        for key, value in shadow_price_limits.items():
            st.write(f"{key}: {value}")
