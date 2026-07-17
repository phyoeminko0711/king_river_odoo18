def migrate(cr, version):
    del version
    cr.execute(
        """
        ALTER TABLE product_template
        ADD COLUMN IF NOT EXISTS brand_id integer
        """
    )
    cr.execute(
        """
        UPDATE product_template AS template
           SET brand_id = source.brand_id
          FROM (
                SELECT DISTINCT ON (product_tmpl_id)
                       product_tmpl_id, brand_id
                  FROM product_product
                 WHERE brand_id IS NOT NULL
                 ORDER BY product_tmpl_id, id
               ) AS source
         WHERE template.id = source.product_tmpl_id
           AND template.brand_id IS NULL
        """
    )
