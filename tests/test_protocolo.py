import unittest

from comun import protocolo as P


class TestDecodificador(unittest.TestCase):
    def test_ida_y_vuelta(self):
        d = P.Decodificador()
        self.assertEqual(d.alimentar(P.codificar({"tipo": "saltar"})), [{"tipo": "saltar"}])

    def test_varios_mensajes_pegados(self):
        d = P.Decodificador()
        datos = P.codificar({"tipo": "inicio"}) + P.codificar({"tipo": "estado", "tick": 1})
        msgs = d.alimentar(datos)
        self.assertEqual([m["tipo"] for m in msgs], ["inicio", "estado"])  # ninguno se pierde

    def test_mensaje_partido_en_dos_lecturas(self):
        d = P.Decodificador()
        datos = P.codificar({"tipo": "estado", "tick": 7})
        self.assertEqual(d.alimentar(datos[:5]), [])
        self.assertEqual(d.alimentar(datos[5:]), [{"tipo": "estado", "tick": 7}])

    def test_byte_a_byte(self):
        d = P.Decodificador()
        datos = P.codificar({"tipo": "saltar"})
        salida = []
        for b in datos:
            salida += d.alimentar(bytes([b]))
        self.assertEqual(salida, [{"tipo": "saltar"}])

    def test_basura_se_descarta_sin_cortar(self):
        d = P.Decodificador()
        datos = b"no es json\n[1,2]\n{\"sin_tipo\":1}\n\xff\xfe\n" + P.codificar({"tipo": "saltar"})
        self.assertEqual(d.alimentar(datos), [{"tipo": "saltar"}])

    def test_linea_enorme_sin_terminador(self):
        d = P.Decodificador()
        with self.assertRaises(ValueError):
            d.alimentar(b"a" * (P.MAX_LINEA + 1))


if __name__ == "__main__":
    unittest.main()
